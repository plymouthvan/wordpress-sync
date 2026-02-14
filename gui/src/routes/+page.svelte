<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import Sidebar from '../components/Sidebar.svelte';
  import TerminalPanel from '../components/TerminalPanel.svelte';
  import Dashboard from '../views/Dashboard.svelte';
  import SiteConfig from '../views/SiteConfig.svelte';
  import SyncPanel from '../views/SyncPanel.svelte';
  import History from '../views/History.svelte';
  import Settings from '../views/Settings.svelte';
  import CommandPreview from '../views/CommandPreview.svelte';
  import HealthCheck from '../views/HealthCheck.svelte';
  import BackupManager from '../views/BackupManager.svelte';
  import AddSiteDialog from '../components/AddSiteDialog.svelte';
  import CliSetupBanner from '../components/CliSetupBanner.svelte';
  import { selectedSite, refreshSiteList } from '$lib/stores/sites';
  import { settings, initSettings } from '$lib/stores/settings';
  import { handleKeydown, type Shortcut } from '$lib/utils/shortcuts';
  import { applyTheme, onSystemThemeChange } from '$lib/utils/theme';

  // The activeView string can be a simple name or a parameterized route
  // like "config:{site}", "sync:{site}:push", "healthcheck:{site}", etc.
  let activeView = $state('dashboard');
  let cleanupThemeListener: (() => void) | null = null;
  let showAddSiteDialog = $state(false);

  // Derived view type for matching in the template
  let viewType = $derived.by(() => {
    if (activeView.startsWith('config:')) return 'site-config';
    if (activeView === 'site-config-new') return 'site-config-new';
    if (activeView.startsWith('sync:')) return 'sync';
    if (activeView.startsWith('history:')) return 'history';
    if (activeView.startsWith('commandpreview:')) return 'commandpreview';
    if (activeView.startsWith('healthcheck:')) return 'healthcheck';
    if (activeView.startsWith('backups:')) return 'backups';
    return activeView; // dashboard, history, settings, site-config, sync, etc.
  });

  // Extract site name from parameterized views
  let viewSiteName = $derived.by(() => {
    for (const prefix of ['config:', 'sync:', 'history:', 'commandpreview:', 'healthcheck:', 'backups:']) {
      if (activeView.startsWith(prefix)) {
        const rest = activeView.substring(prefix.length);
        // For sync:{site}:{direction}, strip the direction part
        const colonIdx = rest.indexOf(':');
        return colonIdx >= 0 ? rest.substring(0, colonIdx) : rest;
      }
    }
    return '';
  });

  // Extract sync direction from sync:{site}:{direction} routes
  let syncDirection = $derived.by(() => {
    if (activeView.startsWith('sync:')) {
      const parts = activeView.substring('sync:'.length).split(':');
      if (parts.length >= 2 && (parts[1] === 'push' || parts[1] === 'pull')) {
        return parts[1] as 'push' | 'pull';
      }
    }
    return undefined;
  });

  // Extract config focus section from config:{site}:{section} routes
  let configFocusSection = $derived.by(() => {
    if (activeView.startsWith('config:')) {
      const parts = activeView.substring('config:'.length).split(':');
      if (parts.length >= 2) {
        return parts[1];
      }
    }
    return undefined;
  });

  // Extract site name filter for history view
  let historySiteFilter = $derived.by(() => {
    if (activeView.startsWith('history:')) {
      return activeView.substring('history:'.length);
    }
    return undefined;
  });

  function navigateTo(view: string) {
    // If this is a parameterized config/sync route, also set selectedSite
    if (view.startsWith('config:')) {
      // config:{site} or config:{site}:{section} — extract just the site name
      const rest = view.substring('config:'.length);
      const colonIdx = rest.indexOf(':');
      const siteName = colonIdx >= 0 ? rest.substring(0, colonIdx) : rest;
      selectedSite.set(siteName);
    } else if (view.startsWith('sync:')) {
      const parts = view.substring('sync:'.length).split(':');
      selectedSite.set(parts[0]);
    } else if (view.startsWith('backups:')) {
      const siteName = view.substring('backups:'.length);
      selectedSite.set(siteName);
    } else if (view === 'site-config-new') {
      selectedSite.set(null);
    }

    activeView = view;
  }

  function selectSiteFromDashboard(name: string) {
    selectedSite.set(name);
    activeView = `config:${name}`;
  }

  function addNewSite() {
    showAddSiteDialog = true;
  }

  function handleSiteCreated(name: string) {
    showAddSiteDialog = false;
    selectedSite.set(name);
    activeView = `config:${name}`;
  }

  // Keyboard shortcuts
  const shortcuts: Shortcut[] = [
    {
      key: 'n',
      meta: true,
      handler: () => addNewSite(),
      description: 'Add new site',
    },
    {
      key: 's',
      meta: true,
      handler: () => {
        // Dispatch save event for SiteConfig view
        if (viewType === 'site-config' || viewType === 'site-config-new') {
          window.dispatchEvent(new CustomEvent('app:save-config'));
        }
      },
      description: 'Save current config',
    },
    {
      key: ',',
      meta: true,
      handler: () => navigateTo('settings'),
      description: 'Open Settings',
    },
    {
      key: 'k',
      meta: true,
      handler: () => {
        window.dispatchEvent(new CustomEvent('app:focus-search'));
      },
      description: 'Focus site search',
    },
  ];

  function onKeydown(event: KeyboardEvent) {
    handleKeydown(event, shortcuts);
  }

  // Apply theme from settings
  function applyCurrentTheme() {
    const theme = $settings.theme;
    applyTheme(theme);
  }

  onMount(async () => {
    await initSettings();
    await refreshSiteList();

    // Apply theme on load
    applyCurrentTheme();

    // Listen for system theme changes
    cleanupThemeListener = onSystemThemeChange(() => {
      if ($settings.theme === 'system') {
        applyTheme('system');
      }
    });
  });

  onDestroy(() => {
    if (cleanupThemeListener) {
      cleanupThemeListener();
    }
  });

  // React to theme changes in settings
  $effect(() => {
    const _theme = $settings.theme;
    applyCurrentTheme();
  });
</script>

<svelte:window onkeydown={onKeydown} />

<div class="app-layout">
  <Sidebar onNavigate={navigateTo} {activeView} onAddSite={addNewSite} />

  <div class="main-column">
    <CliSetupBanner />

    <main class="main-content">
      {#if viewType === 'dashboard'}
        <Dashboard onSelectSite={selectSiteFromDashboard} onNavigate={navigateTo} onAddSite={addNewSite} />
      {:else if viewType === 'site-config' || viewType === 'site-config-new'}
        <SiteConfig onNavigate={navigateTo} focusSection={configFocusSection} />
      {:else if viewType === 'sync'}
        <SyncPanel initialDirection={syncDirection} onNavigate={navigateTo} />
      {:else if viewType === 'history'}
        <History filterSite={historySiteFilter} onNavigate={navigateTo} />
      {:else if viewType === 'settings'}
        <Settings />
      {:else if viewType === 'commandpreview'}
        <CommandPreview siteName={viewSiteName} />
      {:else if viewType === 'healthcheck'}
        <HealthCheck siteName={viewSiteName} />
      {:else if viewType === 'backups'}
        <BackupManager siteName={viewSiteName} onNavigate={navigateTo} />
      {/if}
    </main>

    <TerminalPanel />
  </div>
</div>

{#if showAddSiteDialog}
  <AddSiteDialog
    onclose={() => { showAddSiteDialog = false; }}
    oncreate={handleSiteCreated}
  />
{/if}

<style>
  .app-layout {
    display: flex;
    height: 100vh;
    overflow: hidden;
  }

  .main-column {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    min-width: 0;
  }

  .main-content {
    flex: 1;
    overflow-y: auto;
    background: var(--bg-primary);
    min-height: 0;
  }
</style>
