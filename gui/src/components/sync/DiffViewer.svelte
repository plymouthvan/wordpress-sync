<script lang="ts">
  import type { DiffEntry } from '$lib/types';
  import {
    buildTree,
    getAggregatedCounts,
    getCheckboxState,
    setNodeSelected,
    countSelected,
    countTotal,
    getExcludedEntries,
    formatSize,
    type TreeNode,
  } from '$lib/utils/diffTree';

  interface Props {
    entries: DiffEntry[];
    onproceed: (selected: DiffEntry[]) => void;
    oncancel: () => void;
  }

  let { entries, onproceed, oncancel }: Props = $props();

  // Filter state
  let searchQuery = $state('');
  let showAdded = $state(true);
  let showModified = $state(true);
  let showDeleted = $state(true);
  let sizeFilter = $state<'all' | '100kb' | '1mb' | '10mb'>('all');
  let showExcludedPanel = $state(false);

  // Build tree from entries, applying filters
  let filteredEntries = $derived.by(() => {
    let result = entries;

    // Filter by change type
    result = result.filter((e) => {
      if (e.change === 'added' && !showAdded) return false;
      if (e.change === 'modified' && !showModified) return false;
      if (e.change === 'deleted' && !showDeleted) return false;
      return true;
    });

    // Filter by search query
    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase();
      result = result.filter((e) => e.path.toLowerCase().includes(q));
    }

    // Filter by size
    if (sizeFilter !== 'all') {
      const minSize =
        sizeFilter === '100kb'
          ? 100 * 1024
          : sizeFilter === '1mb'
            ? 1024 * 1024
            : 10 * 1024 * 1024;
      result = result.filter((e) => (e.size ?? 0) >= minSize);
    }

    return result;
  });

  // Tree state — managed manually to preserve expand/collapse state.
  // We rebuild the tree when filteredEntries change, but preserve expanded paths.
  let tree: ReturnType<typeof buildTree> = $state(buildTree([]));
  let treeVersion = $state(0); // bump to trigger re-render after in-place mutations
  let lastFilteredJson = '';

  // Rebuild tree when filtered entries change, preserving expanded state
  $effect(() => {
    const json = JSON.stringify(filteredEntries.map(e => e.path));
    if (json !== lastFilteredJson) {
      lastFilteredJson = json;
      tree = buildTree(filteredEntries, tree);
    }
  });

  // Summary counts from the full (unfiltered) entry set
  let totalCounts = $derived.by(() => {
    const added = entries.filter((e) => e.change === 'added').length;
    const modified = entries.filter((e) => e.change === 'modified').length;
    const deleted = entries.filter((e) => e.change === 'deleted').length;
    return { added, modified, deleted, total: entries.length };
  });

  let totalSizeBytes = $derived(
    entries.reduce((acc, e) => acc + (e.size ?? 0), 0),
  );

  let selectedCount = $derived.by(() => {
    // treeVersion dependency ensures recalc after selection changes
    const _v = treeVersion;
    return entries.filter((e) => e.selected).length;
  });

  let excludedCount = $derived(entries.length - selectedCount);

  let excludedEntries = $derived.by(() => {
    const _v = treeVersion;
    return getExcludedEntries(tree);
  });

  function toggleNodeSelection(node: TreeNode) {
    const currentState = getCheckboxState(node);
    const newSelected = currentState !== 'checked';
    setNodeSelected(node, newSelected);

    // Sync back to entries array
    syncTreeToEntries(node, newSelected);
    treeVersion++;
  }

  function syncTreeToEntries(node: TreeNode, selected: boolean) {
    if (node.children.length === 0) {
      const entry = entries.find((e) => e.path === node.path);
      if (entry) entry.selected = selected;
    } else {
      for (const child of node.children) {
        syncTreeToEntries(child, selected);
      }
    }
  }

  function toggleExpand(node: TreeNode) {
    node.expanded = !node.expanded;
    treeVersion++;
  }

  function clearAllExclusions() {
    for (const entry of entries) {
      entry.selected = true;
    }
    treeVersion++;
  }

  function resetFilters() {
    searchQuery = '';
    showAdded = true;
    showModified = true;
    showDeleted = true;
    sizeFilter = 'all';
  }

  function handleProceed() {
    const selected = entries.filter((e) => e.selected);
    onproceed(selected);
  }

  let exportFeedback: string | null = $state(null);
  let exportFeedbackTimer: ReturnType<typeof setTimeout> | null = null;

  function showExportFeedback(msg: string) {
    exportFeedback = msg;
    if (exportFeedbackTimer) clearTimeout(exportFeedbackTimer);
    exportFeedbackTimer = setTimeout(() => { exportFeedback = null; }, 3000);
  }

  function buildDiffText(): string {
    const lines: string[] = [];
    lines.push('Sync Diff Report');
    lines.push('================');
    lines.push('');
    lines.push(
      `Total: ${totalCounts.total} files (${totalCounts.added} added, ${totalCounts.modified} modified, ${totalCounts.deleted} deleted)`,
    );
    lines.push(
      `Selected: ${selectedCount} of ${totalCounts.total} (${excludedCount} excluded)`,
    );
    lines.push('');

    for (const entry of entries) {
      const marker = entry.selected ? '[x]' : '[ ]';
      const changeIcon =
        entry.change === 'added'
          ? '+'
          : entry.change === 'modified'
            ? '~'
            : '-';
      const size = entry.size ? ` (${formatSize(entry.size)})` : '';
      lines.push(`${marker} ${changeIcon} ${entry.path}${size}`);
    }

    return lines.join('\n');
  }

  async function exportDiff() {
    const text = buildDiffText();
    try {
      const { save } = await import('@tauri-apps/plugin-dialog');
      const { writeTextFile } = await import('@tauri-apps/plugin-fs');
      const path = await save({
        defaultPath: `sync-diff-${Date.now()}.txt`,
        filters: [{ name: 'Text', extensions: ['txt'] }],
      });
      if (path) {
        await writeTextFile(path, text);
        showExportFeedback(`Saved to ${path.split('/').pop()}`);
        return;
      }
      // User cancelled the dialog — fall through to clipboard
    } catch {
      // Dialog not available — fall through to clipboard
    }

    // Clipboard fallback
    try {
      await navigator.clipboard.writeText(text);
      showExportFeedback('Copied to clipboard');
    } catch {
      showExportFeedback('Export failed');
    }
  }

  function changeIcon(change: 'added' | 'modified' | 'deleted' | undefined): string {
    switch (change) {
      case 'added':
        return '+';
      case 'modified':
        return '~';
      case 'deleted':
        return '\u2212'; // −
      default:
        return '';
    }
  }

  function changeClass(change: 'added' | 'modified' | 'deleted' | undefined): string {
    switch (change) {
      case 'added':
        return 'change-added';
      case 'modified':
        return 'change-modified';
      case 'deleted':
        return 'change-deleted';
      default:
        return '';
    }
  }
</script>

<!-- Summary Bar -->
<div class="diff-summary-bar">
  <div class="summary-stats">
    <span class="stat">
      <span class="stat-icon change-added">+</span>
      {totalCounts.added} to add
    </span>
    <span class="stat-sep">|</span>
    <span class="stat">
      <span class="stat-icon change-modified">~</span>
      {totalCounts.modified} to modify
    </span>
    <span class="stat-sep">|</span>
    <span class="stat">
      <span class="stat-icon change-deleted">&minus;</span>
      {totalCounts.deleted} to delete
    </span>
    {#if totalSizeBytes > 0}
      <span class="stat-sep">|</span>
      <span class="stat">{formatSize(totalSizeBytes)} total</span>
    {/if}
  </div>
  <div class="summary-selection">
    Selected: {selectedCount} of {totalCounts.total} files
    {#if excludedCount > 0}
      &mdash; {excludedCount} excluded
    {/if}
  </div>
</div>

<!-- Filter Toolbar -->
<div class="diff-toolbar">
  <input
    type="text"
    class="search-input"
    placeholder="Search files..."
    bind:value={searchQuery}
  />
  <div class="filter-toggles">
    <button
      class="filter-btn"
      class:active={showAdded}
      class:change-added-bg={showAdded}
      onclick={() => (showAdded = !showAdded)}
    >
      + Added
    </button>
    <button
      class="filter-btn"
      class:active={showModified}
      class:change-modified-bg={showModified}
      onclick={() => (showModified = !showModified)}
    >
      ~ Modified
    </button>
    <button
      class="filter-btn"
      class:active={showDeleted}
      class:change-deleted-bg={showDeleted}
      onclick={() => (showDeleted = !showDeleted)}
    >
      &minus; Deleted
    </button>
  </div>
  <select class="size-filter" bind:value={sizeFilter}>
    <option value="all">Show all sizes</option>
    <option value="100kb">&gt; 100 KB</option>
    <option value="1mb">&gt; 1 MB</option>
    <option value="10mb">&gt; 10 MB</option>
  </select>
  <button class="reset-btn" onclick={resetFilters}>Reset</button>
</div>

<!-- Tree View -->
<div class="diff-tree-container">
  {#if filteredEntries.length === 0}
    <div class="tree-empty">
      No files match the current filters.
    </div>
  {:else}
    <div class="tree-view">
      {#each tree.children as node (node.path)}
        {@render treeNodeSnippet(node, 0)}
      {/each}
    </div>
  {/if}
</div>

<!-- Excluded Panel -->
{#if excludedCount > 0}
  <div class="excluded-panel">
    <button
      class="excluded-header"
      onclick={() => (showExcludedPanel = !showExcludedPanel)}
    >
      <span class="excluded-toggle">{showExcludedPanel ? '\u25BC' : '\u25B6'}</span>
      <span>{excludedCount} excluded item{excludedCount !== 1 ? 's' : ''}</span>
    </button>
    {#if showExcludedPanel}
      <div class="excluded-list">
        {#each excludedEntries as item (item.path)}
          <div class="excluded-item">
            <span class="excluded-path">{item.path}</span>
          </div>
        {/each}
        <button class="clear-exclusions-btn" onclick={clearAllExclusions}>
          Clear All Exclusions
        </button>
      </div>
    {/if}
  </div>
{/if}

<!-- Action Buttons -->
<div class="diff-actions">
  <button class="btn btn-secondary" onclick={oncancel}>Cancel</button>
  <button class="btn btn-secondary" onclick={exportDiff}>Export Diff</button>
  {#if exportFeedback}
    <span class="export-feedback">{exportFeedback}</span>
  {/if}
  <button class="btn btn-primary" onclick={handleProceed}>
    Sync {selectedCount} file{selectedCount !== 1 ? 's' : ''}
    {#if excludedCount > 0}
      ({excludedCount} excluded)
    {/if}
  </button>
</div>

{#snippet treeNodeSnippet(node: TreeNode, depth: number)}
  {@const isDir = node.children.length > 0}
  {@const cbState = getCheckboxState(node)}
  {@const counts = isDir ? getAggregatedCounts(node) : null}

  <div class="tree-row" style="padding-left: {depth * 20 + 4}px">
    <!-- Expand/collapse for directories -->
    {#if isDir}
      <button class="expand-btn" onclick={() => toggleExpand(node)}>
        {node.expanded ? '\u25BC' : '\u25B6'}
      </button>
    {:else}
      <span class="expand-spacer"></span>
    {/if}

    <!-- Tri-state checkbox -->
    <label class="tree-checkbox">
      <input
        type="checkbox"
        checked={cbState === 'checked'}
        indeterminate={cbState === 'indeterminate'}
        onchange={() => toggleNodeSelection(node)}
      />
    </label>

    <!-- Change type icon -->
    {#if node.change}
      <span class="change-icon {changeClass(node.change)}">{changeIcon(node.change)}</span>
    {:else if isDir}
      <span class="change-icon dir-icon">{'\uD83D\uDCC1'}</span>
    {/if}

    <!-- Name -->
    <span class="node-name" class:is-dir={isDir}>
      {node.name}
      {#if isDir && node.children.length > 0}
        /
      {/if}
    </span>

    <!-- Size (for files) -->
    {#if node.size}
      <span class="node-size">{formatSize(node.size)}</span>
    {/if}

    <!-- Aggregate counts for directories -->
    {#if counts && (counts.added > 0 || counts.modified > 0 || counts.deleted > 0)}
      <span class="dir-counts">
        ({#if counts.added > 0}<span class="change-added">+{counts.added}</span>{/if}{#if counts.added > 0 && (counts.modified > 0 || counts.deleted > 0)}, {/if}{#if counts.modified > 0}<span class="change-modified">~{counts.modified}</span>{/if}{#if counts.modified > 0 && counts.deleted > 0}, {/if}{#if counts.deleted > 0}<span class="change-deleted">-{counts.deleted}</span>{/if})
      </span>
    {/if}
  </div>

  {#if isDir && node.expanded}
    {#each node.children as child (child.path)}
      {@render treeNodeSnippet(child, depth + 1)}
    {/each}
  {/if}
{/snippet}

<style>
  /* Summary Bar */
  .diff-summary-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 16px;
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    margin-bottom: 8px;
  }

  .summary-stats {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
  }

  .stat {
    display: flex;
    align-items: center;
    gap: 4px;
    color: var(--text-secondary);
  }

  .stat-icon {
    font-weight: 700;
    font-size: 14px;
  }

  .stat-sep {
    color: var(--text-muted);
  }

  .summary-selection {
    font-size: 12px;
    color: var(--text-muted);
  }

  /* Filter Toolbar */
  .diff-toolbar {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 0;
    flex-wrap: wrap;
  }

  .search-input {
    flex: 1;
    min-width: 180px;
    padding: 6px 10px;
    font-size: 13px;
  }

  .filter-toggles {
    display: flex;
    gap: 4px;
  }

  .filter-btn {
    padding: 5px 10px;
    font-size: 12px;
    font-weight: 500;
    border-radius: var(--radius-sm);
    border: 1px solid var(--border-color);
    background: var(--bg-input);
    color: var(--text-muted);
    transition: all 0.15s ease;
  }

  .filter-btn.active {
    color: var(--text-primary);
    border-color: var(--text-muted);
  }

  .filter-btn.change-added-bg.active {
    border-color: var(--success);
    color: var(--success);
    background: rgba(34, 197, 94, 0.1);
  }

  .filter-btn.change-modified-bg.active {
    border-color: var(--warning);
    color: var(--warning);
    background: rgba(234, 179, 8, 0.1);
  }

  .filter-btn.change-deleted-bg.active {
    border-color: var(--error);
    color: var(--error);
    background: rgba(239, 68, 68, 0.1);
  }

  .size-filter {
    padding: 5px 8px;
    font-size: 12px;
    border-radius: var(--radius-sm);
  }

  .reset-btn {
    padding: 5px 10px;
    font-size: 12px;
    font-weight: 500;
    border-radius: var(--radius-sm);
    background: var(--bg-hover);
    color: var(--text-muted);
    transition: all 0.15s ease;
  }

  .reset-btn:hover {
    color: var(--text-primary);
    background: var(--border-color);
  }

  /* Tree View */
  .diff-tree-container {
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    background: var(--bg-card);
    max-height: 400px;
    overflow-y: auto;
    overflow-x: auto;
  }

  .tree-view {
    padding: 4px 0;
  }

  .tree-empty {
    padding: 40px 20px;
    text-align: center;
    color: var(--text-muted);
    font-size: 13px;
  }

  .tree-row {
    display: flex;
    align-items: center;
    gap: 6px;
    padding-top: 3px;
    padding-bottom: 3px;
    padding-right: 12px;
    font-size: 13px;
    cursor: default;
  }

  .tree-row:hover {
    background: var(--bg-hover);
  }

  .expand-btn {
    width: 18px;
    height: 18px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 10px;
    color: var(--text-muted);
    flex-shrink: 0;
    border-radius: 2px;
  }

  .expand-btn:hover {
    background: var(--border-color);
    color: var(--text-primary);
  }

  .expand-spacer {
    width: 18px;
    flex-shrink: 0;
  }

  .tree-checkbox {
    display: flex;
    align-items: center;
    flex-shrink: 0;
  }

  .tree-checkbox input {
    width: 14px;
    height: 14px;
    margin: 0;
    cursor: pointer;
    accent-color: var(--accent);
  }

  .change-icon {
    width: 16px;
    text-align: center;
    font-weight: 700;
    font-size: 14px;
    flex-shrink: 0;
  }

  .dir-icon {
    font-size: 13px;
    font-weight: normal;
  }

  .change-added {
    color: var(--success);
  }

  .change-modified {
    color: var(--warning);
  }

  .change-deleted {
    color: var(--error);
  }

  .node-name {
    color: var(--text-primary);
    white-space: nowrap;
  }

  .node-name.is-dir {
    font-weight: 500;
  }

  .node-size {
    margin-left: auto;
    font-size: 11px;
    color: var(--text-muted);
    font-family: var(--font-mono);
    white-space: nowrap;
  }

  .dir-counts {
    margin-left: 8px;
    font-size: 11px;
    color: var(--text-muted);
    white-space: nowrap;
  }

  /* Excluded Panel */
  .excluded-panel {
    margin-top: 8px;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    overflow: hidden;
  }

  .excluded-header {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 8px 12px;
    font-size: 12px;
    font-weight: 500;
    color: var(--text-secondary);
    background: var(--bg-secondary);
    text-align: left;
    transition: background 0.15s ease;
  }

  .excluded-header:hover {
    background: var(--bg-hover);
  }

  .excluded-toggle {
    font-size: 10px;
    color: var(--text-muted);
  }

  .excluded-list {
    padding: 8px 12px;
    background: var(--bg-card);
    max-height: 160px;
    overflow-y: auto;
  }

  .excluded-item {
    padding: 3px 0;
    font-size: 12px;
  }

  .excluded-path {
    color: var(--text-muted);
    font-family: var(--font-mono);
  }

  .clear-exclusions-btn {
    margin-top: 8px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 500;
    border-radius: var(--radius-sm);
    background: var(--bg-hover);
    color: var(--text-secondary);
    transition: all 0.15s ease;
  }

  .clear-exclusions-btn:hover {
    background: var(--border-color);
    color: var(--text-primary);
  }

  /* Action Buttons */
  .diff-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-top: 16px;
    padding-top: 16px;
    border-top: 1px solid var(--border-color);
  }

  .btn {
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 500;
    border-radius: var(--radius-sm);
    transition: all 0.15s ease;
  }

  .btn-secondary {
    background: var(--bg-hover);
    color: var(--text-secondary);
  }

  .btn-secondary:hover {
    background: var(--border-color);
    color: var(--text-primary);
  }

  .btn-primary {
    background: var(--accent);
    color: #fff;
  }

  .btn-primary:hover {
    background: var(--accent-hover);
  }

  .export-feedback {
    font-size: 12px;
    color: var(--success);
    align-self: center;
    animation: fadeIn 0.2s ease;
  }

  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }
</style>
