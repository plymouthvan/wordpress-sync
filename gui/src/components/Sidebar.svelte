<script lang="ts">
  import { onMount } from 'svelte';
  import { sites, selectedSite, refreshSiteList } from '$lib/stores/sites';
  import StatusBadge from './StatusBadge.svelte';

  interface Props {
    onNavigate: (view: string) => void;
    activeView: string;
    onAddSite: () => void;
  }

  let { onNavigate, activeView, onAddSite }: Props = $props();

  let searchQuery = $state('');

  let filteredSites = $derived.by(() => {
    if (!searchQuery.trim()) return $sites;
    const q = searchQuery.toLowerCase();
    return $sites.filter((site) => site.name.toLowerCase().includes(q));
  });

  function selectSite(name: string) {
    selectedSite.set(name);
    onNavigate(`sync:${name}`);
  }

  function isSiteActive(siteName: string): boolean {
    return (
      $selectedSite === siteName &&
      (activeView.startsWith('config:') || activeView.startsWith('sync:') || activeView.startsWith('backups:'))
    );
  }

  onMount(() => {
    refreshSiteList();
  });
</script>

<aside class="sidebar">
  <div class="sidebar-header">
    <h1 class="app-title">WordPress Sync</h1>
  </div>

  <div class="sidebar-section">
    <div class="section-header">
      <span class="section-label">Sites</span>
      <button class="add-btn" onclick={onAddSite} title="Add new site">+</button>
    </div>

    {#if $sites.length > 3}
      <div class="search-row">
        <input
          type="text"
          placeholder="Filter sites..."
          class="sidebar-search"
          bind:value={searchQuery}
        />
      </div>
    {/if}

    <nav class="site-list">
      {#each filteredSites as site (site.name)}
        <button
          class="site-item"
          class:active={isSiteActive(site.name)}
          onclick={() => selectSite(site.name)}
        >
          <StatusBadge status={site.status} />
          <span class="site-name truncate">{site.name}</span>
        </button>
      {:else}
        {#if searchQuery.trim()}
          <p class="empty-state">No matching sites</p>
        {:else}
          <p class="empty-state">No sites configured</p>
        {/if}
      {/each}
    </nav>
  </div>

  <div class="sidebar-footer">
    <button
      class="footer-link"
      class:active={activeView === 'dashboard'}
      onclick={() => onNavigate('dashboard')}
    >
      <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
        <path d="M8 1L1 5.5V14h5V10h4v4h5V5.5L8 1z" />
      </svg>
      Dashboard
    </button>
    <button
      class="footer-link"
      class:active={activeView === 'history' || activeView.startsWith('history:')}
      onclick={() => onNavigate('history')}
    >
      <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
        <path
          d="M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1zm0 12.5A5.5 5.5 0 1 1 8 2.5a5.5 5.5 0 0 1 0 11zM8.5 4H7v5l4.3 2.5.7-1.2-3.5-2V4z"
        />
      </svg>
      History
    </button>
    <button
      class="footer-link"
      class:active={activeView.startsWith('backups')}
      onclick={() => {
        const site = $selectedSite;
        onNavigate(site ? `backups:${site}` : 'dashboard');
      }}
    >
      <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
        <path d="M3 4h10v9H3V4zm3-2h4v2H6V2zM7 7v4h2V7H7zM6 8h4v2H6V8z" />
      </svg>
      Backups
    </button>
    <button
      class="footer-link"
      class:active={activeView === 'settings'}
      onclick={() => onNavigate('settings')}
    >
      <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
        <path
          d="M8 10a2 2 0 1 0 0-4 2 2 0 0 0 0 4zm6.3-2.8l-1.1-.2c-.1-.4-.3-.7-.5-1l.6-1-1.3-1.3-1 .6c-.3-.2-.7-.4-1-.5l-.2-1.1H7.2l-.2 1.1c-.4.1-.7.3-1 .5l-1-.6L3.7 5l.6 1c-.2.3-.4.7-.5 1l-1.1.2v1.6l1.1.2c.1.4.3.7.5 1l-.6 1L5 12.3l1-.6c.3.2.7.4 1 .5l.2 1.1h1.6l.2-1.1c.4-.1.7-.3 1-.5l1 .6 1.3-1.3-.6-1c.2-.3.4-.7.5-1l1.1-.2V7.2z"
        />
      </svg>
      Settings
    </button>
  </div>
</aside>

<style>
  .sidebar {
    width: var(--sidebar-width);
    height: 100vh;
    background: var(--bg-sidebar);
    border-right: 1px solid var(--border-color);
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
  }

  .sidebar-header {
    padding: 16px 20px;
    border-bottom: 1px solid var(--border-color);
  }

  .app-title {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
    letter-spacing: -0.01em;
  }

  .sidebar-section {
    flex: 1;
    overflow-y: auto;
    padding: 12px 0;
  }

  .section-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 4px 20px 8px;
  }

  .section-label {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-muted);
  }

  .add-btn {
    width: 22px;
    height: 22px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--radius-sm);
    color: var(--text-muted);
    font-size: 16px;
    font-weight: 500;
    transition: all 0.15s ease;
  }

  .add-btn:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
  }

  .search-row {
    padding: 0 12px 8px;
  }

  .sidebar-search {
    width: 100%;
    padding: 6px 10px;
    font-size: 12px;
    background: var(--bg-input);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    color: var(--text-primary);
  }

  .sidebar-search:focus {
    border-color: var(--accent);
    outline: none;
  }

  .site-list {
    display: flex;
    flex-direction: column;
    gap: 1px;
  }

  .site-item {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    padding: 8px 20px;
    text-align: left;
    color: var(--text-secondary);
    transition: all 0.1s ease;
  }

  .site-item:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
  }

  .site-item.active {
    background: var(--accent-subtle);
    color: var(--accent);
  }

  .site-name {
    font-size: 13px;
    font-weight: 500;
  }

  .empty-state {
    padding: 20px;
    text-align: center;
    color: var(--text-muted);
    font-size: 13px;
  }

  .sidebar-footer {
    border-top: 1px solid var(--border-color);
    padding: 8px 8px;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .footer-link {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    padding: 8px 12px;
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    font-size: 13px;
    font-weight: 500;
    text-align: left;
    transition: all 0.1s ease;
  }

  .footer-link:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
  }

  .footer-link.active {
    background: var(--accent-subtle);
    color: var(--accent);
  }
</style>
