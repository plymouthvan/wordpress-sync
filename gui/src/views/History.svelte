<script lang="ts">
  import { onMount } from 'svelte';
  import { sites } from '$lib/stores/sites';
  import { loadHistory, deleteHistoryEntry } from '$lib/services/history';
  import type { SyncHistoryEntry } from '$lib/types';
  import LogViewer from '../components/history/LogViewer.svelte';

  interface Props {
    filterSite?: string;
    onNavigate?: (view: string) => void;
  }

  let { filterSite, onNavigate }: Props = $props();

  // State
  let entries = $state<SyncHistoryEntry[]>([]);
  let loading = $state(true);
  let searchQuery = $state('');
  let statusFilter = $state<'all' | 'success' | 'failed' | 'cancelled'>('all');
  let siteFilter = $state<string>('');
  let displayCount = $state(50);
  let logViewerEntry = $state<SyncHistoryEntry | null>(null);
  let deleteConfirmId = $state<string | null>(null);

  // Initialize site filter from prop
  $effect(() => {
    if (filterSite) {
      siteFilter = filterSite;
    }
  });

  // Derived: unique site names from history
  let siteNames = $derived.by(() => {
    const names = new Set(entries.map((e) => e.site_name));
    return Array.from(names).sort();
  });

  // Derived: filtered entries
  let filteredEntries = $derived.by(() => {
    let list = entries;

    // Site filter
    if (siteFilter) {
      list = list.filter((e) => e.site_name === siteFilter);
    }

    // Status filter
    if (statusFilter !== 'all') {
      list = list.filter((e) => e.status === statusFilter);
    }

    // Text search
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter(
        (e) =>
          e.site_name.toLowerCase().includes(q) ||
          e.direction.toLowerCase().includes(q) ||
          e.sync_type.toLowerCase().includes(q)
      );
    }

    return list;
  });

  // Derived: visible entries (pagination)
  let visibleEntries = $derived(filteredEntries.slice(0, displayCount));
  let hasMore = $derived(filteredEntries.length > displayCount);

  function formatDate(dateStr: string): string {
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return dateStr;
    }
  }

  function formatDuration(seconds: number): string {
    if (seconds < 60) return `${seconds}s`;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    if (mins < 60) return `${mins}m ${secs}s`;
    const hours = Math.floor(mins / 60);
    const remainMins = mins % 60;
    return `${hours}h ${remainMins}m`;
  }

  function syncTypeLabel(type: string): string {
    switch (type) {
      case 'full': return 'Full';
      case 'files-only': return 'Files Only';
      case 'db-only': return 'DB Only';
      default: return type;
    }
  }

  function handleViewLog(entry: SyncHistoryEntry) {
    logViewerEntry = entry;
  }

  function handleRerun(entry: SyncHistoryEntry) {
    onNavigate?.(`sync:${entry.site_name}:${entry.direction}`);
  }

  async function handleDelete(id: string) {
    try {
      await deleteHistoryEntry(id);
      entries = entries.filter((e) => e.id !== id);
    } catch (e) {
      console.error('Failed to delete entry:', e);
    }
    deleteConfirmId = null;
  }

  function loadMore() {
    displayCount += 50;
  }

  async function fetchHistory() {
    loading = true;
    try {
      entries = await loadHistory();
    } catch (e) {
      console.error('Failed to load history:', e);
      entries = [];
    }
    loading = false;
  }

  onMount(() => {
    fetchHistory();
  });
</script>

<div class="view-container">
  <header class="view-header">
    <h2>Sync History</h2>
    <p class="subtitle">View past sync operations and their outcomes</p>
  </header>

  <!-- Filters -->
  <div class="filters-bar">
    <div class="search-wrap">
      <svg class="search-icon" width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5">
        <circle cx="6" cy="6" r="4.5" />
        <line x1="9.5" y1="9.5" x2="13" y2="13" />
      </svg>
      <input
        type="text"
        placeholder="Search history..."
        class="search-input"
        bind:value={searchQuery}
      />
    </div>

    <select class="filter-select" bind:value={statusFilter}>
      <option value="all">All Statuses</option>
      <option value="success">Success</option>
      <option value="failed">Failed</option>
      <option value="cancelled">Cancelled</option>
    </select>

    <select class="filter-select" bind:value={siteFilter}>
      <option value="">All Sites</option>
      {#each siteNames as name}
        <option value={name}>{name}</option>
      {/each}
    </select>
  </div>

  {#if loading}
    <div class="loading-state">
      <div class="spinner"></div>
      <p>Loading history...</p>
    </div>
  {:else if entries.length === 0}
    <div class="empty-state">
      <div class="empty-icon">
        <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.5">
          <circle cx="24" cy="24" r="16" />
          <polyline points="24,14 24,24 32,28" />
        </svg>
      </div>
      <h3>No sync history yet</h3>
      <p>Run a sync operation to see it appear here.</p>
    </div>
  {:else if filteredEntries.length === 0}
    <div class="empty-state">
      <h3>No matching entries</h3>
      <p>Try adjusting your filters</p>
    </div>
  {:else}
    <div class="table-wrapper">
      <table class="history-table">
        <thead>
          <tr>
            <th>Timestamp</th>
            <th>Site</th>
            <th>Direction</th>
            <th>Type</th>
            <th>Duration</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {#each visibleEntries as entry (entry.id)}
            <tr>
              <td class="col-timestamp">{formatDate(entry.started_at)}</td>
              <td class="col-site">{entry.site_name}</td>
              <td class="col-direction">
                <span class="direction-badge" class:push={entry.direction === 'push'} class:pull={entry.direction === 'pull'}>
                  {entry.direction === 'push' ? '\u2191 Push' : '\u2193 Pull'}
                </span>
              </td>
              <td class="col-type">{syncTypeLabel(entry.sync_type)}</td>
              <td class="col-duration">{formatDuration(entry.duration_seconds)}</td>
              <td class="col-status">
                <span class="status-label" class:success={entry.status === 'success'} class:failed={entry.status === 'failed'} class:cancelled={entry.status === 'cancelled'}>
                  {#if entry.status === 'success'}
                    <span class="status-icon">{'\u2713'}</span> Success
                  {:else if entry.status === 'failed'}
                    <span class="status-icon">{'\u2717'}</span> Failed
                  {:else}
                    <span class="status-icon">{'\u2298'}</span> Cancelled
                  {/if}
                </span>
              </td>
              <td class="col-actions">
                <button class="table-btn" onclick={() => handleViewLog(entry)} title="View Log">
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5">
                    <rect x="2" y="1" width="10" height="12" rx="1" />
                    <line x1="4" y1="4" x2="10" y2="4" />
                    <line x1="4" y1="7" x2="10" y2="7" />
                    <line x1="4" y1="10" x2="8" y2="10" />
                  </svg>
                </button>
                <button class="table-btn" onclick={() => handleRerun(entry)} title="Re-run">
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M11 7A4 4 0 1 1 7 3" />
                    <polyline points="7,1 11,3 7,5" />
                  </svg>
                </button>
                {#if deleteConfirmId === entry.id}
                  <button class="table-btn confirm-delete" onclick={() => handleDelete(entry.id)} title="Confirm delete">
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="2">
                      <polyline points="3,7 6,10 11,4" />
                    </svg>
                  </button>
                  <button class="table-btn" onclick={() => { deleteConfirmId = null; }} title="Cancel">
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="2">
                      <line x1="3" y1="3" x2="11" y2="11" />
                      <line x1="11" y1="3" x2="3" y2="11" />
                    </svg>
                  </button>
                {:else}
                  <button class="table-btn delete-btn" onclick={() => { deleteConfirmId = entry.id; }} title="Delete">
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5">
                      <polyline points="3,4 4,12 10,12 11,4" />
                      <line x1="2" y1="4" x2="12" y2="4" />
                      <path d="M5 4V3a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1v1" />
                    </svg>
                  </button>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    {#if hasMore}
      <div class="load-more-row">
        <button class="btn btn-secondary" onclick={loadMore}>
          Load More ({filteredEntries.length - displayCount} remaining)
        </button>
      </div>
    {/if}
  {/if}
</div>

{#if logViewerEntry}
  <LogViewer
    entry={logViewerEntry}
    onclose={() => { logViewerEntry = null; }}
  />
{/if}

<style>
  .view-container {
    padding: 32px;
    max-width: 1100px;
  }

  .view-header {
    margin-bottom: 20px;
  }

  .view-header h2 {
    font-size: 24px;
    font-weight: 600;
    margin-bottom: 4px;
  }

  .subtitle {
    color: var(--text-secondary);
    font-size: 14px;
  }

  /* Filters */
  .filters-bar {
    display: flex;
    gap: 12px;
    align-items: center;
    margin-bottom: 20px;
    flex-wrap: wrap;
  }

  .search-wrap {
    position: relative;
    flex: 1;
    min-width: 200px;
    max-width: 320px;
  }

  .search-icon {
    position: absolute;
    left: 10px;
    top: 50%;
    transform: translateY(-50%);
    color: var(--text-muted);
    pointer-events: none;
  }

  .search-input {
    width: 100%;
    padding-left: 32px;
    font-size: 13px;
  }

  .filter-select {
    width: 160px;
    font-size: 13px;
  }

  /* Loading */
  .loading-state {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 80px 20px;
    justify-content: center;
    color: var(--text-muted);
    font-size: 14px;
  }

  .spinner {
    width: 20px;
    height: 20px;
    border: 2px solid var(--border-color);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  /* Empty state */
  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 80px 20px;
    background: var(--bg-card);
    border: 1px dashed var(--border-color);
    border-radius: var(--radius-md);
    text-align: center;
    color: var(--text-muted);
  }

  .empty-icon {
    margin-bottom: 16px;
    opacity: 0.4;
  }

  .empty-state h3 {
    font-size: 18px;
    font-weight: 600;
    color: var(--text-secondary);
    margin-bottom: 8px;
  }

  .empty-state p {
    font-size: 14px;
  }

  /* Table */
  .table-wrapper {
    overflow-x: auto;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
  }

  .history-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }

  .history-table thead {
    background: var(--bg-card);
    border-bottom: 1px solid var(--border-color);
  }

  .history-table th {
    padding: 10px 14px;
    text-align: left;
    font-weight: 600;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
    white-space: nowrap;
  }

  .history-table td {
    padding: 10px 14px;
    border-bottom: 1px solid var(--border-light);
    vertical-align: middle;
  }

  .history-table tbody tr:hover {
    background: var(--bg-hover);
  }

  .history-table tbody tr:last-child td {
    border-bottom: none;
  }

  .col-timestamp {
    white-space: nowrap;
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--text-secondary);
  }

  .col-site {
    font-weight: 500;
  }

  .col-duration {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--text-secondary);
  }

  .col-type {
    color: var(--text-secondary);
  }

  .direction-badge {
    display: inline-flex;
    align-items: center;
    gap: 2px;
    padding: 2px 8px;
    border-radius: var(--radius-sm);
    font-size: 11px;
    font-weight: 600;
  }

  .direction-badge.push {
    background: rgba(239, 68, 68, 0.12);
    color: var(--error);
  }

  .direction-badge.pull {
    background: rgba(34, 197, 94, 0.12);
    color: var(--success);
  }

  .status-label {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 12px;
    font-weight: 500;
  }

  .status-label.success { color: var(--success); }
  .status-label.failed { color: var(--error); }
  .status-label.cancelled { color: var(--text-muted); }

  .status-icon {
    font-weight: 700;
  }

  .col-actions {
    display: flex;
    gap: 4px;
    white-space: nowrap;
  }

  .table-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border-radius: var(--radius-sm);
    color: var(--text-muted);
    transition: all 0.15s ease;
  }

  .table-btn:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
  }

  .delete-btn:hover {
    background: rgba(239, 68, 68, 0.1);
    color: var(--error);
  }

  .confirm-delete {
    background: rgba(239, 68, 68, 0.1);
    color: var(--error);
  }

  .confirm-delete:hover {
    background: rgba(239, 68, 68, 0.2);
  }

  /* Load More */
  .load-more-row {
    display: flex;
    justify-content: center;
    padding: 20px;
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
</style>
