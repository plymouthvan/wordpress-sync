<script lang="ts">
  import { sites } from '$lib/stores/sites';

  interface Props {
    onclose: () => void;
    oncreate: (name: string) => void;
  }

  let { onclose, oncreate }: Props = $props();

  let siteName = $state('');
  let error = $state('');

  let slug = $derived(
    siteName
      .toLowerCase()
      .replace(/[^a-z0-9\s-]/g, '')
      .replace(/\s+/g, '-')
      .replace(/-+/g, '-')
      .replace(/^-|-$/g, '')
  );

  let filename = $derived(slug ? `${slug}.yaml` : '');

  function validate(): boolean {
    if (!siteName.trim()) {
      error = 'Site name is required';
      return false;
    }

    if (!slug) {
      error = 'Site name must contain at least one alphanumeric character';
      return false;
    }

    // Check for duplicate
    const existing = $sites.map((s) => s.name);
    if (existing.includes(slug)) {
      error = `A site named "${slug}" already exists`;
      return false;
    }

    error = '';
    return true;
  }

  async function handleCreate() {
    if (!validate()) return;

    try {
      const { saveSiteConfig } = await import('$lib/services/config');
      const { refreshSiteList } = await import('$lib/stores/sites');
      const defaultConfig = {
        name: slug,
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
        operation: { direction: 'push' as const }
      };

      await saveSiteConfig(slug, defaultConfig);
      await refreshSiteList();
      oncreate(slug);
    } catch (e) {
      error = `Failed to create site: ${e}`;
    }
  }

  function handleOverlayClick(e: MouseEvent) {
    if (e.target === e.currentTarget) onclose();
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') onclose();
    if (e.key === 'Enter') handleCreate();
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="modal-overlay" onclick={handleOverlayClick}>
  <div class="modal-content" role="dialog" aria-modal="true" aria-label="Add New Site">
    <div class="modal-header">
      <h3>Add New Site</h3>
      <button class="close-btn" onclick={onclose} aria-label="Close">&times;</button>
    </div>

    <div class="modal-body">
      <div class="field">
        <label class="field-label" for="site-name">Site Name</label>
        <input
          id="site-name"
          type="text"
          bind:value={siteName}
          placeholder="e.g. Acme Corp"
          class="field-input"
          autofocus
        />
        {#if filename}
          <p class="filename-preview">
            Config file: <code>{filename}</code>
          </p>
        {/if}
      </div>

      {#if error}
        <div class="error-msg">{error}</div>
      {/if}
    </div>

    <div class="modal-footer">
      <button class="btn btn-secondary" onclick={onclose}>Cancel</button>
      <button class="btn btn-primary" onclick={handleCreate} disabled={!slug}>Create Site</button>
    </div>
  </div>
</div>

<style>
  .modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
    padding: 24px;
  }

  .modal-content {
    background: var(--bg-primary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    width: 100%;
    max-width: 460px;
    box-shadow: var(--shadow-lg);
  }

  .modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 20px 24px 0;
  }

  .modal-header h3 {
    font-size: 18px;
    font-weight: 600;
  }

  .close-btn {
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    color: var(--text-muted);
    border-radius: var(--radius-sm);
    transition: all 0.15s ease;
  }

  .close-btn:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
  }

  .modal-body {
    padding: 20px 24px;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .field-label {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-secondary);
  }

  .field-input {
    font-size: 14px;
    padding: 10px 14px;
  }

  .filename-preview {
    font-size: 12px;
    color: var(--text-muted);
  }

  .filename-preview code {
    font-family: var(--font-mono);
    background: var(--bg-hover);
    padding: 1px 6px;
    border-radius: 3px;
    font-size: 12px;
  }

  .error-msg {
    margin-top: 12px;
    padding: 8px 12px;
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.3);
    border-radius: var(--radius-sm);
    color: var(--error);
    font-size: 13px;
  }

  .modal-footer {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    padding: 0 24px 20px;
  }

  .btn {
    padding: 8px 20px;
    font-size: 13px;
    font-weight: 500;
    border-radius: var(--radius-sm);
    transition: all 0.15s ease;
  }

  .btn-primary {
    background: var(--accent);
    color: #fff;
  }

  .btn-primary:hover:not(:disabled) {
    background: var(--accent-hover);
  }

  .btn-primary:disabled {
    opacity: 0.5;
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
