<script lang="ts">
  import { onMount, tick } from 'svelte';
  import YAML from 'yaml';
  import { selectedSite } from '$lib/stores/sites';
  import { loadSiteConfig, saveSiteConfig, normalizeBackupConfig, normalizeDbTempConfig } from '$lib/services/config';
  import type { SiteConfig } from '$lib/types';
  import CollapsibleSection from '../components/config/CollapsibleSection.svelte';
  import SectionSSH from '../components/config/SectionSSH.svelte';
  import SectionPaths from '../components/config/SectionPaths.svelte';
  import SectionDomains from '../components/config/SectionDomains.svelte';
  import SectionRsync from '../components/config/SectionRsync.svelte';
  import SectionOwnership from '../components/config/SectionOwnership.svelte';
  import SectionBackup from '../components/config/SectionBackup.svelte';
  import SectionValidation from '../components/config/SectionValidation.svelte';
  import SectionPlugins from '../components/config/SectionPlugins.svelte';
  import SectionOperation from '../components/config/SectionOperation.svelte';
  import RawYamlEditor from '../components/config/RawYamlEditor.svelte';

  interface Props {
    onNavigate?: (view: string) => void;
    focusSection?: string;
  }
  let { onNavigate, focusSection }: Props = $props();

  const DEFAULT_CONFIG: SiteConfig = {
    name: '',
    ssh: { user: '', host: '', port: 22, key_path: '', sudo: { user: '', key_path: '' } },
    paths: { local: '', live: '', db_temp: { local: '/tmp', remote: '/tmp' }, db_filename: 'database.sql' },
    domains: {
      staging: { http: '', https: '' },
      live: { http: '', https: '' }
    },
    rsync: {
      dry_run: true,
      delete: false,
      progress: true,
      verbose: false,
      compress: true,
      chmod_files: '644',
      chmod_dirs: '755',
      excludes: [],
      cleanup_files: []
    },
    ownership: { user: 'www-data', group: 'www-data' },
    backup: {
      enabled: true,
      directory: { local: '../wordpress-sync-backups', remote: '../wordpress-sync-backups' },
      archive_format: 'wordpress-sync-backup_%Y-%m-%d_%H%M%S',
      cleanup_prompt: true,
      database: {
        enabled: true,
        filename_format: 'db-%Y%m%d-%H%M%S.sql'
      }
    },
    validation: {
      enabled: true,
      checks: {
        core_files: { enabled: true, verify_checksums: true, critical_files: [] },
        database: { enabled: true, verify_core_tables: true, additional_tables: [] },
        accessibility: { homepage: true, wp_admin: true }
      }
    },
    plugins: {
      live: { activate: [], deactivate: [] },
      local: { activate: [], deactivate: [] }
    },
    operation: { direction: 'push' }
  };

  let siteName = $derived($selectedSite ?? '');

  let config = $state<SiteConfig>(structuredClone(DEFAULT_CONFIG));
  let savedConfigJson = $state('');
  let loading = $state(true);
  let loadError = $state('');
  let saving = $state(false);
  let saveMessage = $state<{ type: 'success' | 'error'; text: string } | null>(null);

  let activeTab = $state<'form' | 'yaml'>('form');

  // Collapsible section open states
  let sshOpen = $state(true);
  let pathsOpen = $state(false);
  let domainsOpen = $state(false);
  let rsyncOpen = $state(false);
  let ownershipOpen = $state(false);
  let backupOpen = $state(false);
  let validationOpen = $state(false);
  let pluginsOpen = $state(false);
  let operationOpen = $state(false);

  let isDirty = $derived(JSON.stringify(config) !== savedConfigJson);

  function deepMergeConfig(base: SiteConfig, loaded: Partial<SiteConfig>): SiteConfig {
    // Deep merge loaded config over defaults so all fields exist
    const result = structuredClone(base);

    if (loaded.ssh) {
      result.ssh = { ...result.ssh, ...loaded.ssh };
      if (loaded.ssh.sudo) {
        result.ssh.sudo = { ...result.ssh.sudo, ...loaded.ssh.sudo };
      }
    }
    if (loaded.paths) result.paths = { ...result.paths, ...loaded.paths };
    if (loaded.domains) {
      if (loaded.domains.staging) result.domains.staging = { ...result.domains.staging, ...loaded.domains.staging };
      if (loaded.domains.live) result.domains.live = { ...result.domains.live, ...loaded.domains.live };
    }
    if (loaded.rsync) result.rsync = { ...result.rsync, ...loaded.rsync };
    if (loaded.ownership) result.ownership = { ...result.ownership, ...loaded.ownership };
    if (loaded.backup) {
      result.backup = { ...result.backup, ...loaded.backup };
      if (loaded.backup.database) {
        result.backup.database = { ...result.backup.database, ...loaded.backup.database };
      }
    }
    if (loaded.validation) {
      result.validation = { ...result.validation, ...loaded.validation };
      if (loaded.validation.checks) {
        result.validation.checks = { ...result.validation.checks, ...loaded.validation.checks };
        if (loaded.validation.checks.core_files) {
          result.validation.checks.core_files = { ...result.validation.checks.core_files, ...loaded.validation.checks.core_files };
        }
        if (loaded.validation.checks.database) {
          result.validation.checks.database = { ...result.validation.checks.database, ...loaded.validation.checks.database };
        }
        if (loaded.validation.checks.accessibility) {
          result.validation.checks.accessibility = { ...result.validation.checks.accessibility, ...loaded.validation.checks.accessibility };
        }
      }
    }
    if (loaded.plugins) {
      if (loaded.plugins.live) result.plugins.live = { ...result.plugins.live, ...loaded.plugins.live };
      if (loaded.plugins.local) result.plugins.local = { ...result.plugins.local, ...loaded.plugins.local };
    }
    if (loaded.operation) result.operation = { ...result.operation, ...loaded.operation };
    if (loaded.name) result.name = loaded.name;

    return result;
  }

  async function loadConfig() {
    loading = true;
    loadError = '';

    if (!siteName) {
      // New site — use defaults
      config = structuredClone(DEFAULT_CONFIG);
      savedConfigJson = JSON.stringify(config);
      loading = false;
      return;
    }

    try {
      const loaded = await loadSiteConfig(siteName);
      let merged = deepMergeConfig(DEFAULT_CONFIG, loaded);
      merged.name = siteName;
      config = normalizeDbTempConfig(normalizeBackupConfig(merged));
      savedConfigJson = JSON.stringify(config);
    } catch (e) {
      console.warn('Failed to load config, using defaults:', e);
      loadError = `Failed to load config: ${e}`;
      config = structuredClone(DEFAULT_CONFIG);
      config.name = siteName;
      savedConfigJson = JSON.stringify(config);
    }

    loading = false;
  }

  async function saveConfig() {
    saving = true;
    saveMessage = null;

    try {
      const name = siteName || config.name || 'new-site';
      await saveSiteConfig(name, config);
      savedConfigJson = JSON.stringify(config);
      saveMessage = { type: 'success', text: 'Configuration saved successfully' };
      setTimeout(() => { saveMessage = null; }, 3000);
    } catch (e) {
      saveMessage = { type: 'error', text: `Failed to save: ${e}` };
    }

    saving = false;
  }

  function updateConfig(updated: SiteConfig) {
    config = updated;
  }

  // Track the last loaded site name to avoid redundant reloads
  let lastLoadedSite = $state<string | undefined>(undefined);

  // Load config on mount and when site changes
  $effect(() => {
    const name = siteName;
    // Only reload when the site name actually changes
    if (name !== lastLoadedSite) {
      lastLoadedSite = name;
      loadConfig();
    }
  });

  // Map section names to their open state setters
  const sectionMap: Record<string, () => void> = {
    ssh: () => { sshOpen = true; },
    paths: () => { pathsOpen = true; },
    domains: () => { domainsOpen = true; },
    rsync: () => { rsyncOpen = true; },
    ownership: () => { ownershipOpen = true; },
    backup: () => { backupOpen = true; },
    validation: () => { validationOpen = true; },
    plugins: () => { pluginsOpen = true; },
    operation: () => { operationOpen = true; },
  };

  // Focus a specific section when requested (e.g. config:site:backup)
  let lastFocusedSection: string | undefined;
  $effect(() => {
    const section = focusSection;
    const isLoaded = !loading;
    if (section && isLoaded && section !== lastFocusedSection) {
      lastFocusedSection = section;
      // Ensure form tab is active
      activeTab = 'form';
      // Open the target section
      const opener = sectionMap[section];
      if (opener) {
        opener();
        // Wait for DOM to update after opening, then scroll into view
        tick().then(() => {
          const el = document.querySelector(`[data-section="${section}"]`);
          if (el) {
            el.scrollIntoView({ behavior: 'smooth', block: 'start' });
            // Brief highlight effect
            el.classList.add('section-highlight');
            setTimeout(() => el.classList.remove('section-highlight'), 2000);
          }
        });
      }
    }
  });
</script>

<div class="site-config">
  <header class="view-header">
    <div class="header-content">
      <div class="header-top">
        <button class="back-btn" onclick={() => onNavigate?.('dashboard')} title="Back to Dashboard">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="14" y1="8" x2="2" y2="8" />
            <polyline points="7,3 2,8 7,13" />
          </svg>
        </button>
        <h2>Site Configuration</h2>
      </div>
      <p class="subtitle">
        {#if siteName}
          Configure sync settings for <strong>{siteName}</strong>
        {:else}
          New site configuration
        {/if}
      </p>
    </div>

    <div class="tab-bar">
      <button
        class="tab"
        class:active={activeTab === 'form'}
        onclick={() => { activeTab = 'form'; }}
        type="button"
      >
        Form
      </button>
      <button
        class="tab"
        class:active={activeTab === 'yaml'}
        onclick={() => { activeTab = 'yaml'; }}
        type="button"
      >
        YAML
      </button>
    </div>
  </header>

  {#if loading}
    <div class="loading-state">
      <p>Loading configuration...</p>
    </div>
  {:else if loadError}
    <div class="error-banner">
      <span>{loadError}</span>
    </div>
  {/if}

  {#if !loading}
    <div class="config-body">
      {#if activeTab === 'form'}
        <div class="sections-list">
          <div data-section="ssh">
            <CollapsibleSection title="SSH Connection" bind:open={sshOpen}>
              <SectionSSH {config} onchange={updateConfig} {siteName} />
            </CollapsibleSection>
          </div>

          <div data-section="paths">
            <CollapsibleSection title="Paths" bind:open={pathsOpen}>
              <SectionPaths {config} onchange={updateConfig} />
            </CollapsibleSection>
          </div>

          <div data-section="domains">
            <CollapsibleSection title="Domains" bind:open={domainsOpen}>
              <SectionDomains {config} onchange={updateConfig} />
            </CollapsibleSection>
          </div>

          <div data-section="rsync">
            <CollapsibleSection title="Rsync Options" bind:open={rsyncOpen}>
              <SectionRsync {config} onchange={updateConfig} />
            </CollapsibleSection>
          </div>

          <div data-section="ownership">
            <CollapsibleSection title="Ownership & Permissions" bind:open={ownershipOpen}>
              <SectionOwnership {config} onchange={updateConfig} />
            </CollapsibleSection>
          </div>

          <div data-section="backup">
            <CollapsibleSection title="Backups" bind:open={backupOpen}>
              <SectionBackup {config} onchange={updateConfig} />
            </CollapsibleSection>
          </div>

          <div data-section="validation">
            <CollapsibleSection title="Validation" bind:open={validationOpen}>
              <SectionValidation {config} onchange={updateConfig} />
            </CollapsibleSection>
          </div>

          <div data-section="plugins">
            <CollapsibleSection title="Plugin Management" bind:open={pluginsOpen}>
              <SectionPlugins {config} onchange={updateConfig} />
            </CollapsibleSection>
          </div>

          <div data-section="operation">
            <CollapsibleSection title="Operation Defaults" bind:open={operationOpen}>
              <SectionOperation {config} onchange={updateConfig} />
            </CollapsibleSection>
          </div>
        </div>
      {:else}
        <div class="yaml-view">
          <RawYamlEditor {config} onchange={updateConfig} />
        </div>
      {/if}
    </div>
  {/if}

  <div class="save-bar">
    <div class="save-bar-left">
      {#if isDirty}
        <span class="dirty-indicator" title="Unsaved changes">*</span>
        <span class="dirty-text">Unsaved changes</span>
      {/if}
    </div>

    <div class="save-bar-right">
      {#if saveMessage}
        <span class="save-message" class:success={saveMessage.type === 'success'} class:error={saveMessage.type === 'error'}>
          {saveMessage.text}
        </span>
      {/if}
      <button
        type="button"
        class="btn-save"
        onclick={saveConfig}
        disabled={saving}
      >
        {saving ? 'Saving...' : 'Save Configuration'}
      </button>
    </div>
  </div>
</div>

<style>
  .site-config {
    display: flex;
    flex-direction: column;
    height: 100%;
    position: relative;
  }

  .view-header {
    padding: 24px 32px 0;
    flex-shrink: 0;
  }

  .header-content {
    margin-bottom: 20px;
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
    margin-bottom: 0;
  }

  .subtitle {
    color: var(--text-secondary);
    font-size: 14px;
  }

  .tab-bar {
    display: flex;
    gap: 0;
    border-bottom: 1px solid var(--border-color);
  }

  .tab {
    padding: 10px 24px;
    font-size: 13px;
    font-weight: 600;
    color: var(--text-secondary);
    border-bottom: 2px solid transparent;
    transition: all 0.15s ease;
    margin-bottom: -1px;
  }

  .tab:hover {
    color: var(--text-primary);
  }

  .tab.active {
    color: var(--accent);
    border-bottom-color: var(--accent);
  }

  .loading-state {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 80px 20px;
    color: var(--text-muted);
    font-size: 14px;
  }

  .error-banner {
    margin: 16px 32px 0;
    padding: 12px 16px;
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid var(--error);
    border-radius: var(--radius-sm);
    color: var(--error);
    font-size: 13px;
  }

  .config-body {
    flex: 1;
    overflow-y: auto;
    padding: 20px 32px 80px;
  }

  .sections-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
    max-width: 900px;
  }

  .yaml-view {
    max-width: 900px;
  }

  .save-bar {
    position: sticky;
    bottom: 0;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 32px;
    background: var(--bg-secondary);
    border-top: 1px solid var(--border-color);
    flex-shrink: 0;
    z-index: 10;
  }

  .save-bar-left {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .dirty-indicator {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
    background: var(--warning);
    color: #000;
    border-radius: 50%;
    font-size: 14px;
    font-weight: 700;
    line-height: 1;
  }

  .dirty-text {
    font-size: 13px;
    color: var(--text-secondary);
  }

  .save-bar-right {
    display: flex;
    align-items: center;
    gap: 16px;
  }

  .save-message {
    font-size: 13px;
    font-weight: 500;
  }

  .save-message.success {
    color: var(--success);
  }

  .save-message.error {
    color: var(--error);
  }

  .btn-save {
    padding: 10px 28px;
    background: var(--accent);
    color: #fff;
    border-radius: var(--radius-sm);
    font-size: 14px;
    font-weight: 600;
    transition: background 0.15s ease;
  }

  .btn-save:hover:not(:disabled) {
    background: var(--accent-hover);
  }

  .btn-save:disabled {
    opacity: 0.6;
  }

  .sections-list :global(.section-highlight) {
    animation: section-pulse 2s ease-out;
  }

  @keyframes section-pulse {
    0% { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: var(--radius-md); }
    70% { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: var(--radius-md); }
    100% { outline: 2px solid transparent; outline-offset: 2px; }
  }
</style>
