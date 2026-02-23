<script lang="ts">
  import { onMount } from 'svelte';
  import { selectedSite } from '$lib/stores/sites';
  import { loadSiteConfig, normalizeBackupConfig } from '$lib/services/config';
  import {
    listAllBackups,
    computeSummary,
    downloadBackup,
    deleteBackup,
    browseBackupContents,
    restoreFileBackup,
    restoreDbBackup,
    getLatestDir,
    getDbBackupDir,
    getBackupRootDir,
    getArchivesDir,
    resolveDbBackupDir,
    type BackupItem,
    type BackupSummary,
    type BackupFileEntry,
  } from '$lib/services/backup';
  import { createBackupCommand, type BackupOptions } from '$lib/services/cli';
  import { termInfo, termError, termSuccess, terminalOpen } from '$lib/stores/terminal';
  import { revealItemInDir } from '@tauri-apps/plugin-opener';
  import type { SiteConfig } from '$lib/types';

  interface Props {
    siteName?: string;
    onNavigate?: (view: string) => void;
  }
  let { siteName, onNavigate }: Props = $props();

  let effectiveSite = $derived(siteName || $selectedSite || '');

  // State
  let config = $state<SiteConfig | null>(null);
  let loading = $state(true);
  let loadError = $state('');
  let items = $state<BackupItem[]>([]);

  // Filters
  let filterCategory = $state<'all' | 'backup-archive' | 'db-backup'>('all');
  let filterLocation = $state<'all' | 'local' | 'remote'>('all');

  // Filtered items
  let filteredItems = $derived.by(() => {
    let list = items;
    if (filterCategory !== 'all') list = list.filter(i => i.category === filterCategory);
    if (filterLocation !== 'all') list = list.filter(i => i.location === filterLocation);
    return list;
  });

  // Summaries
  let totalSummary = $derived(computeSummary(items));
  let filteredSummary = $derived(computeSummary(filteredItems));
  let backupFileSummary = $derived(computeSummary(items.filter(i => i.category === 'backup-latest' || i.category === 'backup-archive')));
  let dbSummary = $derived(computeSummary(items.filter(i => i.category === 'db-backup')));

  // Action state
  let actionInProgress = $state<string | null>(null); // item path being acted on
  let actionMessage = $state<{ type: 'success' | 'error'; text: string } | null>(null);

  // Browse state
  let browsingItem = $state<BackupItem | null>(null);
  let browseContents = $state<BackupFileEntry[]>([]);
  let browseLoading = $state(false);

  // Manual backup state
  let manualBackupInProgress = $state(false);

  // Bulk selection state
  let selectedPaths = $state<Set<string>>(new Set());
  let selectedItems = $derived(
    filteredItems.filter(i => selectedPaths.has(i.path))
  );
  let selectedSummary = $derived(computeSummary(selectedItems));
  let allSelected = $derived(
    filteredItems.length > 0 && filteredItems.every(i => selectedPaths.has(i.path))
  );
  let someSelected = $derived(selectedPaths.size > 0);
  let selectedRemoteItems = $derived(selectedItems.filter(i => i.location === 'remote'));
  let bulkInProgress = $state(false);
  let bulkProgressMessage = $state('');

  // Path display
  let backupRootLocal = $derived(config ? getBackupRootDir(config, 'local') : '');
  let backupRootRemote = $derived(config ? getBackupRootDir(config, 'remote') : '');
  let latestDirLocal = $derived(config ? getLatestDir(config, 'local') : '');
  let latestDirRemote = $derived(config ? getLatestDir(config, 'remote') : '');
  let archivesDirLocal = $derived(config ? getArchivesDir(config, 'local') : '');
  let archivesDirRemote = $derived(config ? getArchivesDir(config, 'remote') : '');
  let dbDirLocal = $derived(config ? getDbBackupDir(config, 'local') : '');
  let dbDirRemote = $derived(config ? getDbBackupDir(config, 'remote') : '');

  async function loadBackups() {
    if (!effectiveSite) return;
    loading = true;
    loadError = '';
    actionMessage = null;

    try {
      const rawConfig = await loadSiteConfig(effectiveSite);
      config = normalizeBackupConfig(rawConfig);
      items = await listAllBackups(config);
    } catch (e) {
      loadError = String(e);
      items = [];
    }
    loading = false;
  }

  async function handleDownload(item: BackupItem) {
    if (!config) return;
    actionInProgress = item.path;
    actionMessage = null;

    try {
      const { save } = await import('@tauri-apps/plugin-dialog');
      const destDir = await save({
        title: 'Save backup to...',
        defaultPath: item.name,
      });
      if (!destDir) {
        actionInProgress = null;
        return;
      }
      // Use the parent directory of the chosen path
      const destFolder = destDir.replace(/\/[^/]+$/, '');

      terminalOpen.set(true);
      termInfo(`Downloading ${item.name} from remote...`);

      const result = await downloadBackup(config, item, destFolder);
      if (result.success) {
        termSuccess(`Downloaded to ${result.localPath}`);
        actionMessage = { type: 'success', text: `Downloaded to ${result.localPath}` };
      } else {
        termError(`Download failed: ${result.error}`);
        actionMessage = { type: 'error', text: result.error ?? 'Download failed' };
      }
    } catch (e) {
      termError(`Download failed: ${e}`);
      actionMessage = { type: 'error', text: String(e) };
    }
    actionInProgress = null;
  }

  async function handleDelete(item: BackupItem) {
    if (!config) return;

    const isLocal = item.location === 'local';
    const { ask } = await import('@tauri-apps/plugin-dialog');

    if (isLocal) {
      // Local: move to macOS Trash (restorable)
      const confirmed = await ask(
        `Move "${item.name}" to Trash?\n\nYou can restore it later from the Finder Trash.`,
        { title: 'Move to Trash' }
      );
      if (!confirmed) return;
    } else {
      // Remote: permanent delete with warning
      const confirmed = await ask(
        `Permanently delete "${item.name}" from remote server?\n\nThis cannot be undone.`,
        { title: 'Delete Remote Backup', kind: 'warning' }
      );
      if (!confirmed) return;
    }

    actionInProgress = item.path;
    actionMessage = null;

    terminalOpen.set(true);
    const verb = isLocal ? 'Moving to Trash' : 'Deleting';
    termInfo(`${verb}: ${item.name}...`);

    const result = await deleteBackup(config, item);
    if (result.success) {
      const msg = result.trashed
        ? `Moved ${item.name} to Trash`
        : `Deleted ${item.name}`;
      termSuccess(msg);
      actionMessage = { type: 'success', text: msg };
      // Remove from list
      items = items.filter(i => i.path !== item.path);
    } else {
      termError(`Failed: ${result.error}`);
      actionMessage = { type: 'error', text: result.error ?? 'Operation failed' };
    }
    actionInProgress = null;
  }

  async function handleBrowse(item: BackupItem) {
    if (!config) return;
    if (browsingItem?.path === item.path) {
      // Toggle off
      browsingItem = null;
      browseContents = [];
      return;
    }

    browsingItem = item;
    browseLoading = true;
    browseContents = [];

    try {
      browseContents = await browseBackupContents(config, item);
    } catch (e) {
      browseContents = [];
    }
    browseLoading = false;
  }

  async function handleRevealInFinder(item: BackupItem) {
    try {
      await revealItemInDir(item.path);
    } catch (e) {
      console.error('Failed to reveal in Finder:', e);
      actionMessage = { type: 'error', text: `Could not show in Finder: ${e}` };
    }
  }

  async function handleRestoreFiles(item: BackupItem) {
    if (!config) return;
    if (item.category !== 'backup-archive' && item.category !== 'backup-latest') return;

    const dest = item.location === 'remote' ? config.paths.live : config.paths.local;
    const side = item.location === 'remote' ? 'remote server' : 'local machine';

    const { ask } = await import('@tauri-apps/plugin-dialog');
    const confirmed = await ask(
      `Restore files from "${item.name}" to the ${side}?\n\nThis will overwrite current files at:\n${dest}\n\nFiles that were changed or deleted during the sync that created this backup will be restored to their previous state.`,
      { title: 'Restore File Backup', kind: 'warning' }
    );
    if (!confirmed) return;

    actionInProgress = item.path;
    actionMessage = null;
    terminalOpen.set(true);
    termInfo(`Restoring files from ${item.name} to ${dest}...`);

    try {
      const result = await restoreFileBackup(config, item);
      if (result.success) {
        termSuccess(result.detail ?? 'Files restored');
        actionMessage = { type: 'success', text: result.detail ?? 'Files restored' };
      } else {
        termError(`Restore failed: ${result.error}`);
        actionMessage = { type: 'error', text: result.error ?? 'Restore failed' };
      }
    } catch (e) {
      termError(`Restore failed: ${e}`);
      actionMessage = { type: 'error', text: String(e) };
    }
    actionInProgress = null;
  }

  async function handleRestoreDb(item: BackupItem) {
    if (!config) return;
    if (item.category !== 'db-backup') return;

    const side = item.location === 'remote' ? 'remote (live)' : 'local';
    const wpPath = item.location === 'remote' ? config.paths.live : config.paths.local;

    const { ask } = await import('@tauri-apps/plugin-dialog');
    const confirmed = await ask(
      `Restore database from "${item.name}" on the ${side} site?\n\nThis will:\n1. Back up the current database first (safety net)\n2. Import ${item.name} into the WordPress database at:\n   ${wpPath}\n\nThe current database will be overwritten.`,
      { title: 'Restore Database Backup', kind: 'warning' }
    );
    if (!confirmed) return;

    actionInProgress = item.path;
    actionMessage = null;
    terminalOpen.set(true);
    termInfo(`Restoring database from ${item.name}...`);
    termInfo('Taking safety backup of current database first...');

    try {
      const result = await restoreDbBackup(config, item);
      if (result.success) {
        const msg = `${result.detail}. Safety backup saved to: ${result.safetyBackupPath}`;
        termSuccess(msg);
        actionMessage = { type: 'success', text: msg };
        // Refresh list to show the new safety backup
        await loadBackups();
      } else {
        const msg = result.error ?? 'Restore failed';
        termError(msg);
        if (result.safetyBackupPath) {
          termInfo(`Safety backup was saved to: ${result.safetyBackupPath}`);
        }
        actionMessage = { type: 'error', text: msg };
      }
    } catch (e) {
      termError(`Restore failed: ${e}`);
      actionMessage = { type: 'error', text: String(e) };
    }
    actionInProgress = null;
  }

  async function handleManualBackup(direction: 'push' | 'pull') {
    if (!config || manualBackupInProgress) return;

    manualBackupInProgress = true;
    actionMessage = null;
    terminalOpen.set(true);

    const location = direction === 'push' ? 'remote' as const : 'local' as const;
    const backupDir = resolveDbBackupDir(config, location);
    const filenameFormat = config.backup?.database?.filename_format || 'manual-backup-%Y%m%d-%H%M%S.sql';

    const opts: BackupOptions = {
      direction,
      ssh: config.ssh,
      paths: config.paths,
      backupDir,
      filenameFormat,
    };

    const target = direction === 'push' ? 'remote (live)' : 'local';
    termInfo(`Taking manual database backup of ${target} site...`);

    try {
      const cmd = createBackupCommand(opts);
      const result = await cmd.execute();
      const output = (result.stdout + '\n' + result.stderr).trim();

      if (result.code === 0 && output.includes('BACKUP_SUCCESS:')) {
        const backupPath = output.split('BACKUP_SUCCESS:').pop()?.trim() ?? '';
        termSuccess(`Database backup saved to: ${backupPath}`);
        actionMessage = { type: 'success', text: `Backup saved: ${backupPath}` };
        // Refresh the list
        await loadBackups();
      } else {
        const errMsg = output || `Backup failed with exit code ${result.code}`;
        termError(`Backup failed: ${errMsg}`);
        actionMessage = { type: 'error', text: errMsg };
      }
    } catch (e) {
      termError(`Backup failed: ${e}`);
      actionMessage = { type: 'error', text: String(e) };
    }

    manualBackupInProgress = false;
  }

  function toggleSelect(item: BackupItem) {
    const next = new Set(selectedPaths);
    if (next.has(item.path)) {
      next.delete(item.path);
    } else {
      next.add(item.path);
    }
    selectedPaths = next;
  }

  function toggleSelectAll() {
    if (allSelected) {
      selectedPaths = new Set();
    } else {
      selectedPaths = new Set(filteredItems.map(i => i.path));
    }
  }

  function clearSelection() {
    selectedPaths = new Set();
  }

  // Clear selection when filters change
  $effect(() => {
    // Read the filter values to establish dependency
    filterCategory;
    filterLocation;
    // Clear selection (use untrack to avoid circular reactivity)
    selectedPaths = new Set();
  });

  async function handleBulkDownload() {
    if (!config || bulkInProgress) return;
    const remoteItems = selectedRemoteItems;
    if (remoteItems.length === 0) return;

    try {
      const { open } = await import('@tauri-apps/plugin-dialog');
      const destDir = await open({
        title: 'Download selected backups to...',
        directory: true,
      });
      if (!destDir) return;

      bulkInProgress = true;
      terminalOpen.set(true);
      termInfo(`Downloading ${remoteItems.length} item(s) to ${destDir}...`);

      let successCount = 0;
      let failCount = 0;

      for (let i = 0; i < remoteItems.length; i++) {
        const item = remoteItems[i];
        bulkProgressMessage = `Downloading ${i + 1}/${remoteItems.length}: ${item.name}`;
        actionMessage = { type: 'success', text: bulkProgressMessage };

        try {
          const result = await downloadBackup(config, item, destDir as string);
          if (result.success) {
            successCount++;
            termSuccess(`  [${i + 1}/${remoteItems.length}] Downloaded ${item.name}`);
          } else {
            failCount++;
            termError(`  [${i + 1}/${remoteItems.length}] Failed: ${item.name} - ${result.error}`);
          }
        } catch (e) {
          failCount++;
          termError(`  [${i + 1}/${remoteItems.length}] Failed: ${item.name} - ${e}`);
        }
      }

      bulkProgressMessage = '';
      const msg = `Downloaded ${successCount} of ${remoteItems.length} item(s)${failCount > 0 ? `, ${failCount} failed` : ''}`;
      termInfo(msg);
      actionMessage = { type: failCount > 0 ? 'error' : 'success', text: msg };
      clearSelection();
    } catch (e) {
      termError(`Bulk download failed: ${e}`);
      actionMessage = { type: 'error', text: String(e) };
    }
    bulkInProgress = false;
  }

  async function handleBulkDelete() {
    if (!config || bulkInProgress) return;
    const toDelete = [...selectedItems];
    if (toDelete.length === 0) return;

    const localCount = toDelete.filter(i => i.location === 'local').length;
    const remoteCount = toDelete.filter(i => i.location === 'remote').length;

    // Build a context-aware confirmation message
    const { ask } = await import('@tauri-apps/plugin-dialog');
    let message: string;
    let title: string;
    let kind: 'info' | 'warning' = 'info';

    if (remoteCount === 0) {
      // All local — trash only
      message = `Move ${localCount} item(s) to Trash?\n\nYou can restore them later from the Finder Trash.`;
      title = 'Move to Trash';
    } else if (localCount === 0) {
      // All remote — permanent delete
      message = `Permanently delete ${remoteCount} item(s) from remote server?\n\nThis cannot be undone.`;
      title = 'Delete Remote Backups';
      kind = 'warning';
    } else {
      // Mixed
      message = `${localCount} local item(s) will be moved to Trash (restorable).\n${remoteCount} remote item(s) will be permanently deleted.\n\nContinue?`;
      title = 'Delete Backups';
      kind = 'warning';
    }

    const confirmed = await ask(message, { title, kind });
    if (!confirmed) return;

    bulkInProgress = true;
    terminalOpen.set(true);
    termInfo(`Processing ${toDelete.length} item(s)...`);

    let trashedCount = 0;
    let deletedCount = 0;
    let failCount = 0;

    for (let i = 0; i < toDelete.length; i++) {
      const item = toDelete[i];
      const verb = item.location === 'local' ? 'Trashing' : 'Deleting';
      bulkProgressMessage = `${verb} ${i + 1}/${toDelete.length}: ${item.name}`;
      actionMessage = { type: 'success', text: bulkProgressMessage };

      try {
        const result = await deleteBackup(config, item);
        if (result.success) {
          if (result.trashed) {
            trashedCount++;
            termSuccess(`  [${i + 1}/${toDelete.length}] Moved to Trash: ${item.name}`);
          } else {
            deletedCount++;
            termSuccess(`  [${i + 1}/${toDelete.length}] Deleted: ${item.name}`);
          }
          // Remove from items list
          items = items.filter(it => it.path !== item.path);
        } else {
          failCount++;
          termError(`  [${i + 1}/${toDelete.length}] Failed: ${item.name} - ${result.error}`);
        }
      } catch (e) {
        failCount++;
        termError(`  [${i + 1}/${toDelete.length}] Failed: ${item.name} - ${e}`);
      }
    }

    bulkProgressMessage = '';
    const parts: string[] = [];
    if (trashedCount > 0) parts.push(`${trashedCount} moved to Trash`);
    if (deletedCount > 0) parts.push(`${deletedCount} permanently deleted`);
    if (failCount > 0) parts.push(`${failCount} failed`);
    const msg = parts.join(', ');
    termInfo(msg);
    actionMessage = { type: failCount > 0 ? 'error' : 'success', text: msg };
    clearSelection();
    bulkInProgress = false;
  }

  function categoryLabel(cat: BackupItem['category']): string {
    switch (cat) {
      case 'backup-archive': return 'Backup Archive';
      case 'backup-latest': return 'Latest Backup';
      case 'db-backup': return 'DB Backup';
    }
  }

  function categoryIcon(cat: BackupItem['category']): string {
    switch (cat) {
      case 'backup-archive': return '\uD83D\uDDC4'; // file cabinet
      case 'backup-latest': return '\uD83D\uDDCE';  // package
      case 'db-backup': return '\uD83D\uDDC3';      // card file box
    }
  }

  onMount(() => {
    loadBackups();
  });
</script>

<div class="view-container">
  <header class="view-header">
    <div class="header-top">
      <button class="back-btn" onclick={() => onNavigate?.('dashboard')} title="Back to Dashboard">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="14" y1="8" x2="2" y2="8" />
          <polyline points="7,3 2,8 7,13" />
        </svg>
      </button>
      <h2>Backup Manager</h2>
    </div>
    <p class="subtitle">
      {#if effectiveSite}
        Manage backups for <strong>{effectiveSite}</strong>
      {:else}
        No site selected
      {/if}
    </p>
  </header>

  {#if loading}
    <div class="loading-state">
      <div class="spinner"></div>
      <p>Scanning backup directories...</p>
    </div>
  {:else if loadError}
    <div class="error-banner">
      <span class="error-icon">{'\u2717'}</span>
      <div>
        <strong>Failed to load backups</strong>
        <p>{loadError}</p>
      </div>
    </div>
  {:else}
    <!-- Summary Cards -->
    <div class="summary-row">
      <div class="summary-card">
        <span class="summary-value">{totalSummary.itemCount}</span>
        <span class="summary-label">Total Items</span>
      </div>
      <div class="summary-card">
        <span class="summary-value">{totalSummary.totalSize}</span>
        <span class="summary-label">Total Size</span>
      </div>
      <div class="summary-card">
        <span class="summary-value">{backupFileSummary.itemCount}</span>
        <span class="summary-label">File Backups</span>
      </div>
      <div class="summary-card">
        <span class="summary-value">{dbSummary.itemCount}</span>
        <span class="summary-label">DB Backups</span>
      </div>
    </div>

    <!-- Paths Info -->
    <details class="paths-info">
      <summary>Backup Directories</summary>
      <div class="paths-grid">
        <span class="path-label">Local Backup Root:</span>
        <code class="path-value">{backupRootLocal}</code>
        <span class="path-label">&nbsp;&nbsp;Latest:</span>
        <code class="path-value">{latestDirLocal}</code>
        <span class="path-label">&nbsp;&nbsp;Archives:</span>
        <code class="path-value">{archivesDirLocal}</code>
        <span class="path-label">&nbsp;&nbsp;DB Backups:</span>
        <code class="path-value">{dbDirLocal}</code>

        <span class="path-label">Remote Backup Root:</span>
        <code class="path-value">{backupRootRemote}</code>
        <span class="path-label">&nbsp;&nbsp;Latest:</span>
        <code class="path-value">{latestDirRemote}</code>
        <span class="path-label">&nbsp;&nbsp;Archives:</span>
        <code class="path-value">{archivesDirRemote}</code>
        <span class="path-label">&nbsp;&nbsp;DB Backups:</span>
        <code class="path-value">{dbDirRemote}</code>
      </div>
    </details>

    <!-- Action Bar -->
    <div class="action-bar">
      <div class="filter-group">
        <select class="filter-select" bind:value={filterCategory}>
          <option value="all">All Types</option>
          <option value="backup-archive">Backup Archives</option>
          <option value="db-backup">DB Backups</option>
        </select>
        <select class="filter-select" bind:value={filterLocation}>
          <option value="all">All Locations</option>
          <option value="local">Local</option>
          <option value="remote">Remote</option>
        </select>
        <span class="filter-summary">
          {filteredSummary.itemCount} item{filteredSummary.itemCount !== 1 ? 's' : ''} ({filteredSummary.totalSize})
        </span>
      </div>
      <div class="action-buttons">
        <button
          class="btn btn-action"
          onclick={() => handleManualBackup('pull')}
          disabled={manualBackupInProgress}
          title="Backup local database now"
        >
          {#if manualBackupInProgress}
            <span class="mini-spinner"></span>
          {:else}
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M6 1v7M3 5l3 3 3-3" /><line x1="2" y1="10" x2="10" y2="10" />
            </svg>
          {/if}
          Backup Local DB
        </button>
        <button
          class="btn btn-action"
          onclick={() => handleManualBackup('push')}
          disabled={manualBackupInProgress}
          title="Backup remote database now"
        >
          {#if manualBackupInProgress}
            <span class="mini-spinner"></span>
          {:else}
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M6 1v7M3 5l3 3 3-3" /><line x1="2" y1="10" x2="10" y2="10" />
            </svg>
          {/if}
          Backup Remote DB
        </button>
        <button class="btn btn-secondary" onclick={loadBackups} title="Refresh backup list">
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M1 6a5 5 0 0 1 9-3M11 6a5 5 0 0 1-9 3" />
            <polyline points="1,2 1,6 5,6" />
            <polyline points="11,10 11,6 7,6" />
          </svg>
          Refresh
        </button>
      </div>
    </div>

    <!-- Action message -->
    {#if actionMessage}
      <div class="action-message" class:success={actionMessage.type === 'success'} class:error={actionMessage.type === 'error'}>
        <span>{actionMessage.type === 'success' ? '\u2713' : '\u2717'}</span>
        <span>{actionMessage.text}</span>
        <button class="dismiss-btn" onclick={() => { actionMessage = null; }}>{'\u2717'}</button>
      </div>
    {/if}

    <!-- Backup Items List -->
    {#if filteredItems.length === 0}
      <div class="empty-state">
        <p>No backups found{filterCategory !== 'all' || filterLocation !== 'all' ? ' matching filters' : ''}.</p>
        {#if items.length === 0}
          <p class="empty-hint">Backups are created automatically during sync when backup is enabled in site configuration.</p>
        {/if}
      </div>
    {:else}
      <!-- Select All Header -->
      <div class="select-all-row">
        <label class="item-checkbox">
          <input
            type="checkbox"
            checked={allSelected}
            indeterminate={someSelected && !allSelected}
            onchange={toggleSelectAll}
            disabled={bulkInProgress}
          />
        </label>
        <span class="select-all-label">
          {#if allSelected}
            All {filteredItems.length} items selected
          {:else if someSelected}
            {selectedPaths.size} of {filteredItems.length} selected
          {:else}
            Select all ({filteredItems.length} items)
          {/if}
        </span>
      </div>

      <!-- Bulk Action Bar -->
      {#if someSelected}
        <div class="bulk-bar">
          <span class="bulk-info">
            {selectedItems.length} item{selectedItems.length !== 1 ? 's' : ''} selected
            ({selectedSummary.totalSize})
          </span>
          <div class="bulk-actions">
            {#if selectedRemoteItems.length > 0}
              <button
                class="btn btn-action"
                onclick={handleBulkDownload}
                disabled={bulkInProgress}
                title="Download {selectedRemoteItems.length} remote item(s)"
              >
                {#if bulkInProgress && bulkProgressMessage.startsWith('Downloading')}
                  <span class="mini-spinner"></span>
                {:else}
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M6 1v7M3 5l3 3 3-3" /><line x1="2" y1="10" x2="10" y2="10" />
                  </svg>
                {/if}
                Download Selected ({selectedRemoteItems.length})
              </button>
            {/if}
            <button
              class="btn btn-danger"
              onclick={handleBulkDelete}
              disabled={bulkInProgress}
              title="Delete {selectedItems.length} item(s)"
            >
              {#if bulkInProgress && bulkProgressMessage.startsWith('Deleting')}
                <span class="mini-spinner"></span>
              {:else}
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5">
                  <path d="M2.5 3.5h7l-.8 7H3.3l-.8-7z" /><line x1="1" y1="3.5" x2="11" y2="3.5" />
                  <path d="M4.5 3.5V2h3v1.5" />
                </svg>
              {/if}
              Delete Selected ({selectedItems.length})
            </button>
            <button class="btn-link" onclick={clearSelection}>
              Clear
            </button>
          </div>
        </div>
      {/if}

      <div class="items-list">
        {#each filteredItems as item (item.path)}
          <div class="backup-item" class:browsing={browsingItem?.path === item.path} class:selected={selectedPaths.has(item.path)}>
            <div class="item-main">
              <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
              <label class="item-checkbox">
                <input
                  type="checkbox"
                  checked={selectedPaths.has(item.path)}
                  onchange={() => toggleSelect(item)}
                  disabled={bulkInProgress}
                />
              </label>
              <div class="item-icon">
                {#if item.type === 'directory'}
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M2 4h4l2 2h6v7H2V4z" />
                  </svg>
                {:else if item.name.endsWith('.sql')}
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
                    <ellipse cx="8" cy="4" rx="5" ry="2" />
                    <path d="M3 4v8c0 1.1 2.2 2 5 2s5-.9 5-2V4" />
                    <path d="M3 8c0 1.1 2.2 2 5 2s5-.9 5-2" />
                  </svg>
                {:else}
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M4 2h5l3 3v9H4V2z" /><polyline points="9,2 9,5 12,5" />
                  </svg>
                {/if}
              </div>

              <div class="item-info">
                <span class="item-name">{item.name}</span>
                <div class="item-meta">
                  <span class="badge badge-category">{categoryLabel(item.category)}</span>
                  <span class="badge" class:badge-local={item.location === 'local'} class:badge-remote={item.location === 'remote'}>
                    {item.location}
                  </span>
                  <span class="item-size">{item.size}</span>
                  <span class="item-date">{item.date}</span>
                </div>
              </div>

              <div class="item-actions">
                {#if item.type === 'directory'}
                  <button
                    class="btn-icon"
                    onclick={() => handleBrowse(item)}
                    title="Browse contents"
                    class:active={browsingItem?.path === item.path}
                  >
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5">
                      <circle cx="6" cy="6" r="4.5" /><line x1="9.5" y1="9.5" x2="13" y2="13" />
                    </svg>
                  </button>
                {/if}
                {#if (item.category === 'backup-archive' || item.category === 'backup-latest') && item.type === 'directory'}
                  <button
                    class="btn-icon btn-restore-icon"
                    onclick={() => handleRestoreFiles(item)}
                    disabled={actionInProgress === item.path}
                    title="Restore files to {item.location === 'remote' ? config?.paths.live : config?.paths.local}"
                  >
                    {#if actionInProgress === item.path}
                      <span class="mini-spinner"></span>
                    {:else}
                      <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M2 7.5a5 5 0 0 1 9.5-1.5" />
                        <polyline points="12,2 12,6 8,6" />
                        <path d="M12 6.5a5 5 0 0 1-9.5 1.5" />
                        <polyline points="2,12 2,8 6,8" />
                      </svg>
                    {/if}
                  </button>
                {/if}
                {#if item.category === 'db-backup'}
                  <button
                    class="btn-icon btn-restore-icon"
                    onclick={() => handleRestoreDb(item)}
                    disabled={actionInProgress === item.path}
                    title="Restore database from this backup"
                  >
                    {#if actionInProgress === item.path}
                      <span class="mini-spinner"></span>
                    {:else}
                      <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M2 7.5a5 5 0 0 1 9.5-1.5" />
                        <polyline points="12,2 12,6 8,6" />
                        <path d="M12 6.5a5 5 0 0 1-9.5 1.5" />
                        <polyline points="2,12 2,8 6,8" />
                      </svg>
                    {/if}
                  </button>
                {/if}
                {#if item.location === 'local'}
                  <button
                    class="btn-icon"
                    onclick={() => handleRevealInFinder(item)}
                    title="Show in Finder"
                  >
                    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M2 4h12M2 4v8a2 2 0 002 2h8a2 2 0 002-2V4M2 4l1.5-2h9L14 4" />
                    </svg>
                  </button>
                {/if}
                {#if item.location === 'remote'}
                  <button
                    class="btn-icon"
                    onclick={() => handleDownload(item)}
                    disabled={actionInProgress === item.path}
                    title="Download to local"
                  >
                    {#if actionInProgress === item.path}
                      <span class="mini-spinner"></span>
                    {:else}
                      <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M7 1v9M4 7l3 3 3-3" /><line x1="2" y1="12" x2="12" y2="12" />
                      </svg>
                    {/if}
                  </button>
                {/if}
                <button
                  class="btn-icon {item.location === 'remote' ? 'btn-danger-icon' : 'btn-delete-icon'}"
                  onclick={() => handleDelete(item)}
                  disabled={actionInProgress === item.path}
                  title={item.location === 'local' ? 'Move to Trash' : 'Delete permanently'}
                >
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M3 4h8l-1 9H4L3 4z" /><line x1="1" y1="4" x2="13" y2="4" />
                    <path d="M5 4V2h4v2" />
                  </svg>
                </button>
              </div>
            </div>

            <!-- Browse panel (expanded) -->
            {#if browsingItem?.path === item.path}
              <div class="browse-panel">
                {#if browseLoading}
                  <div class="browse-loading"><span class="mini-spinner"></span> Loading contents...</div>
                {:else if browseContents.length === 0}
                  <p class="browse-empty">No files found.</p>
                {:else}
                  <div class="browse-header">
                    <span>{browseContents.length} file{browseContents.length !== 1 ? 's' : ''}</span>
                  </div>
                  <div class="browse-list">
                    {#each browseContents as entry}
                      <div class="browse-entry">
                        <span class="browse-path">{entry.path}</span>
                        <span class="browse-size">{entry.size}</span>
                      </div>
                    {/each}
                  </div>
                {/if}
              </div>
            {/if}
          </div>
        {/each}
      </div>
    {/if}
  {/if}
</div>

<style>
  .view-container {
    padding: 32px;
    max-width: 1000px;
  }

  .view-header {
    margin-bottom: 24px;
  }

  .header-top {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 4px;
  }

  .back-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border-radius: var(--radius-sm);
    color: var(--text-muted);
    transition: all 0.15s ease;
    flex-shrink: 0;
  }

  .back-btn:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
  }

  .view-header h2 {
    font-size: 24px;
    font-weight: 600;
  }

  .subtitle {
    color: var(--text-secondary);
    font-size: 14px;
  }

  /* Loading / Error */
  .loading-state {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 60px 20px;
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

  @keyframes spin { to { transform: rotate(360deg); } }

  .error-banner {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 12px 14px;
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.3);
    border-radius: var(--radius-md);
    color: var(--error);
    font-size: 13px;
  }

  .error-icon {
    font-weight: 700;
    font-size: 16px;
    flex-shrink: 0;
  }

  /* Summary Cards */
  .summary-row {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 16px;
  }

  .summary-card {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    padding: 14px 16px;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .summary-value {
    font-size: 20px;
    font-weight: 700;
    color: var(--text-primary);
  }

  .summary-label {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
  }

  /* Paths Info */
  .paths-info {
    margin-bottom: 16px;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    background: var(--bg-card);
    font-size: 13px;
  }

  .paths-info summary {
    padding: 10px 16px;
    cursor: pointer;
    font-weight: 600;
    color: var(--text-secondary);
    user-select: none;
  }

  .paths-info summary:hover {
    color: var(--text-primary);
  }

  .paths-grid {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 6px 12px;
    padding: 0 16px 12px;
  }

  .path-label {
    font-weight: 600;
    color: var(--text-muted);
    font-size: 12px;
    white-space: nowrap;
  }

  .path-value {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--text-secondary);
    word-break: break-all;
  }

  /* Action Bar */
  .action-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 16px;
    flex-wrap: wrap;
  }

  .filter-group {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .filter-select {
    font-size: 12px;
    padding: 5px 8px;
    border-radius: var(--radius-sm);
    background: var(--bg-input);
    border: 1px solid var(--border-color);
    color: var(--text-primary);
  }

  .filter-summary {
    font-size: 12px;
    color: var(--text-muted);
    margin-left: 4px;
  }

  .action-buttons {
    display: flex;
    gap: 6px;
  }

  .btn {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 500;
    border-radius: var(--radius-sm);
    transition: all 0.15s ease;
  }

  .btn-action {
    background: rgba(34, 197, 94, 0.1);
    color: var(--success);
  }

  .btn-action:hover:not(:disabled) {
    background: rgba(34, 197, 94, 0.2);
  }

  .btn-action:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-secondary {
    background: var(--bg-hover);
    color: var(--text-secondary);
  }

  .btn-secondary:hover {
    background: var(--border-color);
    color: var(--text-primary);
  }

  .mini-spinner {
    display: inline-block;
    width: 12px;
    height: 12px;
    border: 1.5px solid var(--border-color);
    border-top-color: currentColor;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  /* Action message */
  .action-message {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    border-radius: var(--radius-sm);
    font-size: 12px;
    margin-bottom: 12px;
  }

  .action-message.success {
    background: rgba(34, 197, 94, 0.1);
    color: var(--success);
  }

  .action-message.error {
    background: rgba(239, 68, 68, 0.1);
    color: var(--error);
  }

  .dismiss-btn {
    margin-left: auto;
    padding: 2px 6px;
    font-size: 11px;
    color: inherit;
    opacity: 0.6;
    border-radius: var(--radius-sm);
  }

  .dismiss-btn:hover {
    opacity: 1;
    background: rgba(0, 0, 0, 0.1);
  }

  /* Empty state */
  .empty-state {
    padding: 60px 20px;
    text-align: center;
    color: var(--text-muted);
    font-size: 14px;
  }

  .empty-hint {
    margin-top: 8px;
    font-size: 12px;
    opacity: 0.7;
  }

  /* Select All Row */
  .select-all-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 14px;
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    margin-bottom: 4px;
  }

  .select-all-label {
    font-size: 12px;
    color: var(--text-muted);
    font-weight: 500;
    user-select: none;
  }

  /* Bulk Action Bar */
  .bulk-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 8px 14px;
    background: var(--accent-subtle);
    border: 1px solid var(--accent);
    border-radius: var(--radius-md);
    margin-bottom: 8px;
    flex-wrap: wrap;
  }

  .bulk-info {
    font-size: 12px;
    font-weight: 600;
    color: var(--accent);
  }

  .bulk-actions {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .btn-danger {
    background: rgba(239, 68, 68, 0.1);
    color: var(--error);
  }

  .btn-danger:hover:not(:disabled) {
    background: rgba(239, 68, 68, 0.2);
  }

  .btn-danger:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-link {
    background: none;
    border: none;
    color: var(--text-muted);
    font-size: 12px;
    padding: 4px 8px;
    cursor: pointer;
    text-decoration: underline;
    text-underline-offset: 2px;
  }

  .btn-link:hover {
    color: var(--text-primary);
  }

  /* Item Checkbox */
  .item-checkbox {
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    cursor: pointer;
  }

  .item-checkbox input[type="checkbox"] {
    width: 15px;
    height: 15px;
    cursor: pointer;
    accent-color: var(--accent);
  }

  /* Items List */
  .items-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .backup-item {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    overflow: hidden;
    transition: border-color 0.15s ease;
  }

  .backup-item:hover {
    border-color: var(--text-muted);
  }

  .backup-item.browsing {
    border-color: var(--accent);
  }

  .backup-item.selected {
    background: var(--accent-subtle);
    border-color: var(--accent);
  }

  .item-main {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 14px;
  }

  .item-icon {
    color: var(--text-muted);
    flex-shrink: 0;
  }

  .item-info {
    flex: 1;
    min-width: 0;
  }

  .item-name {
    display: block;
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    font-family: var(--font-mono);
  }

  .item-meta {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-top: 3px;
    flex-wrap: wrap;
  }

  .badge {
    padding: 1px 6px;
    border-radius: var(--radius-sm);
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }

  .badge-category {
    background: var(--accent-subtle);
    color: var(--accent);
  }

  .badge-local {
    background: rgba(34, 197, 94, 0.1);
    color: var(--success);
  }

  .badge-remote {
    background: rgba(234, 179, 8, 0.1);
    color: var(--warning);
  }

  .item-size {
    font-size: 11px;
    color: var(--text-muted);
    font-family: var(--font-mono);
  }

  .item-date {
    font-size: 11px;
    color: var(--text-muted);
  }

  .item-actions {
    display: flex;
    gap: 4px;
    flex-shrink: 0;
  }

  .btn-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border-radius: var(--radius-sm);
    color: var(--text-muted);
    transition: all 0.15s ease;
  }

  .btn-icon:hover:not(:disabled) {
    background: var(--bg-hover);
    color: var(--text-primary);
  }

  .btn-icon.active {
    background: var(--accent-subtle);
    color: var(--accent);
  }

  .btn-icon:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .btn-danger-icon:hover:not(:disabled) {
    background: rgba(239, 68, 68, 0.1);
    color: var(--error);
  }

  .btn-delete-icon:hover:not(:disabled) {
    background: var(--bg-hover);
    color: var(--text-secondary);
  }

  .btn-restore-icon:hover:not(:disabled) {
    background: rgba(34, 197, 94, 0.1);
    color: var(--success);
  }

  /* Browse Panel */
  .browse-panel {
    border-top: 1px solid var(--border-color);
    padding: 10px 14px;
    background: var(--bg-secondary);
    max-height: 300px;
    overflow-y: auto;
  }

  .browse-loading {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: var(--text-muted);
    padding: 8px 0;
  }

  .browse-empty {
    font-size: 12px;
    color: var(--text-muted);
    font-style: italic;
  }

  .browse-header {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 6px;
  }

  .browse-list {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .browse-entry {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 3px 6px;
    border-radius: var(--radius-sm);
    font-size: 12px;
    font-family: var(--font-mono);
  }

  .browse-entry:hover {
    background: var(--bg-hover);
  }

  .browse-path {
    color: var(--text-secondary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    min-width: 0;
  }

  .browse-size {
    color: var(--text-muted);
    flex-shrink: 0;
    font-size: 11px;
  }
</style>
