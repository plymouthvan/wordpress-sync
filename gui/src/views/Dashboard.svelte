<script lang="ts">
  import { sites, refreshSiteList } from '$lib/stores/sites';
  import type { SiteEntry } from '$lib/stores/sites';
  import StatusBadge from '../components/StatusBadge.svelte';
  import { loadSiteConfig } from '$lib/services/config';
  import type { SiteConfig } from '$lib/types';
  import { onMount } from 'svelte';

  interface Props {
    onSelectSite?: (name: string) => void;
    onNavigate?: (view: string) => void;
    onAddSite?: () => void;
  }

  let { onSelectSite, onNavigate, onAddSite }: Props = $props();

  // Search and sort
  let searchQuery = $state('');
  let sortBy = $state<'name' | 'last-sync' | 'status'>('name');

  // Site configs cache (loaded on mount for domain info)
  let siteConfigs = $state<Record<string, SiteConfig>>({});
  let loading = $state(true);

  // Filtered and sorted sites
  let filteredSites = $derived.by(() => {
    let list = $sites;

    // Filter by search
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter((site) => {
        const cfg = siteConfigs[site.name];
        return (
          site.name.toLowerCase().includes(q) ||
          (cfg?.domains?.staging?.https ?? '').toLowerCase().includes(q) ||
          (cfg?.domains?.live?.https ?? '').toLowerCase().includes(q) ||
          (cfg?.ssh?.host ?? '').toLowerCase().includes(q)
        );
      });
    }

    // Sort
    const sorted = [...list];
    if (sortBy === 'name') {
      sorted.sort((a, b) => a.name.localeCompare(b.name));
    } else if (sortBy === 'last-sync') {
      sorted.sort((a, b) => {
        const aTime = a.lastSync ? new Date(a.lastSync.started_at).getTime() : 0;
        const bTime = b.lastSync ? new Date(b.lastSync.started_at).getTime() : 0;
        return bTime - aTime;
      });
    } else if (sortBy === 'status') {
      const order: Record<string, number> = { error: 0, syncing: 1, ready: 2, unknown: 3 };
      sorted.sort((a, b) => (order[a.status] ?? 4) - (order[b.status] ?? 4));
    }

    return sorted;
  });

  function relativeTime(dateStr: string): string {
    const now = Date.now();
    const then = new Date(dateStr).getTime();
    const seconds = Math.floor((now - then) / 1000);

    if (seconds < 60) return 'just now';
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    if (days < 30) return `${days}d ago`;
    const months = Math.floor(days / 30);
    return `${months}mo ago`;
  }

  function badgeStatus(site: SiteEntry): 'unknown' | 'ready' | 'syncing' | 'error' | 'success' | 'failed' | 'cancelled' {
    if (site.lastSync) {
      if (site.lastSync.status === 'failed') return 'failed';
      if (site.lastSync.status === 'success') return 'success';
    }
    if (site.status === 'error') return 'error';
    if (site.status === 'syncing') return 'syncing';
    if (!site.lastSync) return 'unknown';
    return 'ready';
  }

  function handlePush(e: MouseEvent, siteName: string) {
    e.stopPropagation();
    onNavigate?.(`sync:${siteName}:push`);
  }

  function handlePull(e: MouseEvent, siteName: string) {
    e.stopPropagation();
    onNavigate?.(`sync:${siteName}:pull`);
  }

  function handleEditConfig(e: MouseEvent, siteName: string) {
    e.stopPropagation();
    onNavigate?.(`config:${siteName}`);
  }

  function handleHistory(e: MouseEvent, siteName: string) {
    e.stopPropagation();
    onNavigate?.(`history:${siteName}`);
  }

  function handleHealthCheck(e: MouseEvent, siteName: string) {
    e.stopPropagation();
    onNavigate?.(`healthcheck:${siteName}`);
  }

  function handleBackups(e: MouseEvent, siteName: string) {
    e.stopPropagation();
    onNavigate?.(`backups:${siteName}`);
  }

  function handleCommandPreview(e: MouseEvent, siteName: string) {
    e.stopPropagation();
    onNavigate?.(`commandpreview:${siteName}`);
  }

  async function loadSiteDetails() {
    loading = true;
    await refreshSiteList();
    const configs: Record<string, SiteConfig> = {};
    for (const site of $sites) {
      try {
        configs[site.name] = await loadSiteConfig(site.name);
      } catch {
        // Config may not be loadable
      }
    }
    siteConfigs = configs;
    loading = false;
  }

  onMount(() => {
    loadSiteDetails();
  });
</script>

<div class="dashboard">
  <header class="dashboard-header">
    <div class="header-top-row">
      <div>
        <h2>Dashboard</h2>
        <p class="subtitle">Overview of all configured WordPress sites</p>
      </div>
      <button class="btn btn-primary add-site-btn" onclick={() => onAddSite?.()}>
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="7" y1="1" x2="7" y2="13" />
          <line x1="1" y1="7" x2="13" y2="7" />
        </svg>
        Add Site
      </button>
    </div>

    <div class="toolbar">
      <div class="search-wrap">
        <svg class="search-icon" width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5">
          <circle cx="6" cy="6" r="4.5" />
          <line x1="9.5" y1="9.5" x2="13" y2="13" />
        </svg>
        <input
          type="text"
          placeholder="Search sites..."
          class="search-input"
          bind:value={searchQuery}
        />
      </div>
      <select class="sort-select" bind:value={sortBy}>
        <option value="name">Name (A-Z)</option>
        <option value="last-sync">Last Sync (newest)</option>
        <option value="status">Status</option>
      </select>
    </div>
  </header>

  {#if loading}
    <div class="loading-state">
      <div class="spinner"></div>
      <p>Loading sites...</p>
    </div>
  {:else if $sites.length === 0}
    <div class="empty-dashboard">
      <div class="empty-icon">
        <svg width="64" height="64" viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="1.5">
          <rect x="8" y="8" width="48" height="48" rx="6" />
          <line x1="32" y1="22" x2="32" y2="42" />
          <line x1="22" y1="32" x2="42" y2="32" />
        </svg>
      </div>
      <h3>No sites configured yet</h3>
      <p>Get started by adding your first WordPress site</p>
      <button class="btn btn-primary empty-add-btn" onclick={() => onAddSite?.()}>
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="7" y1="1" x2="7" y2="13" />
          <line x1="1" y1="7" x2="13" y2="7" />
        </svg>
        Add Site
      </button>
    </div>
  {:else if filteredSites.length === 0}
    <div class="empty-dashboard">
      <h3>No matching sites</h3>
      <p>Try adjusting your search query</p>
    </div>
  {:else}
    <div class="cards-grid">
      {#each filteredSites as site (site.name)}
        {@const cfg = siteConfigs[site.name]}
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <div class="site-card" role="button" tabindex="0" onclick={() => onNavigate?.(`sync:${site.name}:${cfg?.operation?.direction ?? 'pull'}`)} onkeydown={(e) => e.key === 'Enter' && onNavigate?.(`sync:${site.name}:${cfg?.operation?.direction ?? 'pull'}`)}>
          <div class="card-header">
            <StatusBadge status={badgeStatus(site)} size="md" />
            <h3 class="card-title">{site.name}</h3>
          </div>

          <div class="card-details">
            {#if cfg?.domains?.staging?.https}
              <div class="detail-row">
                <span class="detail-label">Staging</span>
                <span class="detail-value truncate">{cfg.domains.staging.https}</span>
              </div>
            {/if}
            {#if cfg?.domains?.live?.https}
              <div class="detail-row">
                <span class="detail-label">Live</span>
                <span class="detail-value truncate">{cfg.domains.live.https}</span>
              </div>
            {/if}
            {#if cfg?.ssh?.host}
              <div class="detail-row">
                <span class="detail-label">SSH</span>
                <span class="detail-value truncate">{cfg.ssh.user}@{cfg.ssh.host}</span>
              </div>
            {/if}
          </div>

          <div class="card-sync-info">
            {#if site.lastSync}
              <div class="last-sync">
                <span class="direction-indicator" class:push={site.lastSync.direction === 'push'} class:pull={site.lastSync.direction === 'pull'}>
                  {site.lastSync.direction === 'push' ? '\u2191 Push' : '\u2193 Pull'}
                </span>
                <span class="sync-time" title={site.lastSync.started_at}>
                  {relativeTime(site.lastSync.started_at)}
                </span>
              </div>
            {:else}
              <span class="never-synced">Never synced</span>
            {/if}
          </div>

          <div class="card-actions">
            <button class="action-btn" onclick={(e) => handlePush(e, site.name)} title="Push to live">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5">
                <line x1="6" y1="10" x2="6" y2="2" />
                <polyline points="2,5 6,1 10,5" />
              </svg>
              Push
            </button>
            <button class="action-btn" onclick={(e) => handlePull(e, site.name)} title="Pull from live">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5">
                <line x1="6" y1="2" x2="6" y2="10" />
                <polyline points="2,7 6,11 10,7" />
              </svg>
              Pull
            </button>
            <button class="action-btn" onclick={(e) => handleEditConfig(e, site.name)} title="Edit config">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M8.5 1.5l2 2L4 10H2v-2l6.5-6.5z" />
              </svg>
              Edit
            </button>
            <button class="action-btn" onclick={(e) => handleHistory(e, site.name)} title="View history">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5">
                <circle cx="6" cy="6" r="5" />
                <polyline points="6,3 6,6 8,7.5" />
              </svg>
              History
            </button>
            <button class="action-btn" onclick={(e) => handleBackups(e, site.name)} title="Manage backups">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M2 3h8v7H2V3z" /><path d="M4 3V1h4v2" /><line x1="6" y1="5" x2="6" y2="8" /><line x1="4.5" y1="6.5" x2="7.5" y2="6.5" />
              </svg>
              Backups
            </button>
            <button class="action-btn" onclick={(e) => handleHealthCheck(e, site.name)} title="Health check">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5">
                <path d="M6 1v10M1 6h10" />
                <circle cx="6" cy="6" r="5" />
              </svg>
              Health
            </button>
            <button class="action-btn" onclick={(e) => handleCommandPreview(e, site.name)} title="Preview commands">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5">
                <polyline points="1,3 4,6 1,9" />
                <line x1="6" y1="9" x2="11" y2="9" />
              </svg>
              Commands
            </button>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .dashboard {
    padding: 32px;
    max-width: 1200px;
  }

  .dashboard-header {
    margin-bottom: 24px;
  }

  .header-top-row {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    margin-bottom: 16px;
  }

  .header-top-row h2 {
    font-size: 24px;
    font-weight: 600;
    margin-bottom: 4px;
  }

  .subtitle {
    color: var(--text-secondary);
    font-size: 14px;
  }

  .toolbar {
    display: flex;
    gap: 12px;
    align-items: center;
  }

  .search-wrap {
    position: relative;
    flex: 1;
    max-width: 360px;
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

  .sort-select {
    width: 180px;
    font-size: 13px;
  }

  .btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 500;
    border-radius: var(--radius-sm);
    transition: all 0.15s ease;
  }

  .btn-primary {
    background: var(--accent);
    color: #fff;
  }

  .btn-primary:hover {
    background: var(--accent-hover);
  }

  .add-site-btn {
    flex-shrink: 0;
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

  /* Cards Grid */
  .cards-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 16px;
  }

  .site-card {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    padding: 20px;
    text-align: left;
    transition: all 0.15s ease;
    width: 100%;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .site-card:hover {
    border-color: var(--accent);
    box-shadow: var(--shadow-md);
  }

  .card-header {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .card-title {
    font-size: 16px;
    font-weight: 600;
  }

  .card-details {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .detail-row {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .detail-label {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--text-muted);
    width: 52px;
    flex-shrink: 0;
  }

  .detail-value {
    font-size: 12px;
    color: var(--text-secondary);
    font-family: var(--font-mono);
  }

  .card-sync-info {
    padding-top: 8px;
    border-top: 1px solid var(--border-light);
  }

  .last-sync {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
  }

  .direction-indicator {
    padding: 1px 6px;
    border-radius: var(--radius-sm);
    font-size: 11px;
    font-weight: 600;
  }

  .direction-indicator.push {
    background: rgba(239, 68, 68, 0.12);
    color: var(--error);
  }

  .direction-indicator.pull {
    background: rgba(34, 197, 94, 0.12);
    color: var(--success);
  }

  .sync-time {
    color: var(--text-muted);
  }

  .never-synced {
    font-size: 12px;
    color: var(--text-muted);
    font-style: italic;
  }

  .card-actions {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    padding-top: 4px;
  }

  .action-btn {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 500;
    border-radius: var(--radius-sm);
    background: var(--bg-hover);
    color: var(--text-secondary);
    transition: all 0.15s ease;
  }

  .action-btn:hover {
    background: var(--border-color);
    color: var(--text-primary);
  }

  /* Empty State */
  .empty-dashboard {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 80px 20px;
    color: var(--text-muted);
    text-align: center;
  }

  .empty-icon {
    margin-bottom: 16px;
    opacity: 0.3;
  }

  .empty-dashboard h3 {
    font-size: 18px;
    font-weight: 600;
    color: var(--text-secondary);
    margin-bottom: 8px;
  }

  .empty-dashboard p {
    font-size: 14px;
    margin-bottom: 20px;
  }

  .empty-add-btn {
    padding: 10px 24px;
    font-size: 14px;
  }
</style>
