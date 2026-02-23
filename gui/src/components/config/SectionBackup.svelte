<script lang="ts">
  import { open } from '@tauri-apps/plugin-dialog';
  import type { SiteConfig } from '$lib/types';
  import { getBackupRootDir, getLatestDir, getArchivesDir, getDbBackupDir } from '$lib/services/backup';

  interface Props {
    config: SiteConfig;
    onchange: (config: SiteConfig) => void;
  }

  let { config, onchange }: Props = $props();

  async function browseLocalPath() {
    const selected = await open({
      multiple: false,
      title: 'Select Local Backup Directory',
      directory: true,
    });
    if (selected) {
      updateLocalPath(selected as string);
    }
  }

  // Extract local/remote paths from the directory (handles both new and legacy formats)
  let localPath = $derived(
    typeof config.backup.directory === 'object' && config.backup.directory !== null
      ? config.backup.directory.local
      : (typeof config.backup.directory === 'string' ? config.backup.directory : '')
  );
  let remotePath = $derived(
    typeof config.backup.directory === 'object' && config.backup.directory !== null
      ? config.backup.directory.remote
      : (typeof config.backup.directory === 'string' ? config.backup.directory : '')
  );

  // Resolved path previews
  let previewLocalRoot = $derived(config.paths.local ? getBackupRootDir(config, 'local') : '');
  let previewLocalLatest = $derived(config.paths.local ? getLatestDir(config, 'local') : '');
  let previewLocalArchives = $derived(config.paths.local ? getArchivesDir(config, 'local') : '');
  let previewLocalDb = $derived(config.paths.local ? getDbBackupDir(config, 'local') : '');

  let previewRemoteRoot = $derived(config.paths.live ? getBackupRootDir(config, 'remote') : '');
  let previewRemoteLatest = $derived(config.paths.live ? getLatestDir(config, 'remote') : '');
  let previewRemoteArchives = $derived(config.paths.live ? getArchivesDir(config, 'remote') : '');
  let previewRemoteDb = $derived(config.paths.live ? getDbBackupDir(config, 'remote') : '');

  function updateTop(key: 'enabled' | 'cleanup_prompt', value: boolean) {
    onchange({ ...config, backup: { ...config.backup, [key]: value } });
  }

  function updateArchiveFormat(value: string) {
    onchange({ ...config, backup: { ...config.backup, archive_format: value } });
  }

  function updateLocalPath(value: string) {
    const currentDir = config.backup.directory;
    const remote = typeof currentDir === 'object' && currentDir !== null
      ? currentDir.remote
      : (typeof currentDir === 'string' ? currentDir : '../wordpress-sync-backups');

    onchange({
      ...config,
      backup: {
        ...config.backup,
        directory: { local: value, remote },
      }
    });
  }

  function updateRemotePath(value: string) {
    const currentDir = config.backup.directory;
    const local = typeof currentDir === 'object' && currentDir !== null
      ? currentDir.local
      : (typeof currentDir === 'string' ? currentDir : '../wordpress-sync-backups');

    onchange({
      ...config,
      backup: {
        ...config.backup,
        directory: { local, remote: value },
      }
    });
  }

  function updateDb(key: 'enabled', value: boolean) {
    onchange({
      ...config,
      backup: {
        ...config.backup,
        database: { ...config.backup.database, [key]: value }
      }
    });
  }

  function updateDbFilenameFormat(value: string) {
    onchange({
      ...config,
      backup: {
        ...config.backup,
        database: { ...config.backup.database, filename_format: value }
      }
    });
  }
</script>

<div class="form-layout">
  <div class="toggles-row">
    <label class="toggle-field">
      <span class="toggle-label">Enable File Backup</span>
      <input
        type="checkbox"
        class="toggle-switch"
        checked={config.backup.enabled}
        onchange={(e) => updateTop('enabled', e.currentTarget.checked)}
      />
    </label>

    <label class="toggle-field">
      <span class="toggle-label">Prompt for Cleanup</span>
      <input
        type="checkbox"
        class="toggle-switch"
        checked={config.backup.cleanup_prompt}
        onchange={(e) => updateTop('cleanup_prompt', e.currentTarget.checked)}
      />
    </label>
  </div>

  <!-- Unified Backup Directory -->
  <div class="directory-section">
    <div class="section-header">
      <span class="section-title">Backup Directory</span>
      <span class="section-hint">Relative paths are resolved against each site's root. Absolute paths are used as-is.</span>
    </div>

    <div class="form-grid">
      <div class="field">
        <label for="backup-dir-local">Local Path</label>
        <div class="input-with-button">
          <input
            id="backup-dir-local"
            type="text"
            value={localPath}
            oninput={(e) => updateLocalPath(e.currentTarget.value)}
            placeholder="../wordpress-sync-backups"
          />
          <button type="button" class="btn-browse" onclick={browseLocalPath}>Browse</button>
        </div>
      </div>

      <div class="field">
        <label for="backup-dir-remote">Remote Path</label>
        <input
          id="backup-dir-remote"
          type="text"
          value={remotePath}
          oninput={(e) => updateRemotePath(e.currentTarget.value)}
          placeholder="../wordpress-sync-backups"
        />
      </div>
    </div>

    <!-- Resolved Path Preview -->
    {#if previewLocalRoot || previewRemoteRoot}
      <div class="path-preview">
        <span class="preview-label">Resolved structure:</span>
        {#if previewLocalRoot}
          <div class="preview-tree">
            <span class="preview-heading">Local</span>
            <code class="preview-path root">{previewLocalRoot}/</code>
            <code class="preview-path sub">latest/</code>
            <code class="preview-path sub">archives/</code>
            <code class="preview-path sub">db/</code>
          </div>
        {/if}
        {#if previewRemoteRoot}
          <div class="preview-tree">
            <span class="preview-heading">Remote</span>
            <code class="preview-path root">{previewRemoteRoot}/</code>
            <code class="preview-path sub">latest/</code>
            <code class="preview-path sub">archives/</code>
            <code class="preview-path sub">db/</code>
          </div>
        {/if}
      </div>
    {/if}
  </div>

  <div class="form-grid">
    <div class="field">
      <label for="backup-archive">Archive Name Format</label>
      <input
        id="backup-archive"
        type="text"
        value={config.backup.archive_format}
        oninput={(e) => updateArchiveFormat(e.currentTarget.value)}
        placeholder="wordpress-sync-backup_%Y-%m-%d_%H%M%S"
      />
      <span class="field-hint">Tokens: %Y (year), %m (month), %d (day), %H (hour), %M (min), %S (sec)</span>
    </div>
  </div>

  <div class="field-separator">
    <span class="separator-label">Database Backup</span>
  </div>

  <div class="toggles-row single">
    <label class="toggle-field">
      <span class="toggle-label">Enable DB Backup</span>
      <input
        type="checkbox"
        class="toggle-switch"
        checked={config.backup.database.enabled}
        onchange={(e) => updateDb('enabled', e.currentTarget.checked)}
      />
    </label>
  </div>

  <div class="form-grid">
    <div class="field">
      <label for="db-backup-filename">DB Backup Filename Format</label>
      <input
        id="db-backup-filename"
        type="text"
        value={config.backup.database.filename_format}
        oninput={(e) => updateDbFilenameFormat(e.currentTarget.value)}
        placeholder="db-backup_%Y-%m-%d_%H%M%S.sql"
      />
      <span class="field-hint">DB backups are stored at &lt;backup_dir&gt;/db/ automatically.</span>
    </div>
  </div>
</div>

<style>
  .form-layout {
    display: flex;
    flex-direction: column;
    gap: 16px;
    padding-top: 12px;
  }

  .toggles-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }

  .toggles-row.single {
    grid-template-columns: 1fr;
    max-width: 50%;
  }

  .toggle-field {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 14px;
    background: var(--bg-primary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    cursor: pointer;
    transition: background 0.15s ease;
  }

  .toggle-field:hover {
    background: var(--bg-hover);
  }

  .toggle-label {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-primary);
  }

  .toggle-switch {
    appearance: none;
    -webkit-appearance: none;
    width: 40px;
    height: 22px;
    background: var(--border-color);
    border-radius: 11px;
    position: relative;
    cursor: pointer;
    transition: background 0.2s ease;
    flex-shrink: 0;
    border: none;
    padding: 0;
  }

  .toggle-switch::after {
    content: '';
    position: absolute;
    top: 3px;
    left: 3px;
    width: 16px;
    height: 16px;
    background: #fff;
    border-radius: 50%;
    transition: transform 0.2s ease;
  }

  .toggle-switch:checked {
    background: var(--accent);
  }

  .toggle-switch:checked::after {
    transform: translateX(18px);
  }

  .toggle-switch:focus {
    box-shadow: 0 0 0 3px var(--accent-subtle);
  }

  /* Directory Section */
  .directory-section {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 14px;
    background: var(--bg-primary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
  }

  .section-header {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .section-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-primary);
  }

  .section-hint {
    font-size: 11px;
    color: var(--text-muted);
    line-height: 1.4;
  }

  /* Path Preview */
  .path-preview {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 10px 12px;
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
  }

  .preview-label {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .preview-tree {
    display: flex;
    flex-direction: column;
    gap: 1px;
  }

  .preview-heading {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-secondary);
    margin-bottom: 2px;
  }

  .preview-path {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--text-muted);
    line-height: 1.6;
  }

  .preview-path.root {
    color: var(--text-secondary);
  }

  .preview-path.sub {
    padding-left: 16px;
  }

  .preview-path.sub::before {
    content: '\251C\2500 ';
    color: var(--border-color);
  }

  .preview-path.sub:last-child::before {
    content: '\2514\2500 ';
  }

  .input-with-button {
    display: flex;
    gap: 8px;
  }

  .input-with-button input {
    flex: 1;
  }

  .btn-browse {
    padding: 8px 16px;
    background: var(--bg-hover);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    font-size: 13px;
    font-weight: 500;
    white-space: nowrap;
    transition: all 0.15s ease;
  }

  .btn-browse:hover {
    background: var(--border-color);
    color: var(--text-primary);
  }

  .form-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .field label {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }

  .field input[type='text'] {
    width: 100%;
  }

  .field-hint {
    font-size: 11px;
    color: var(--text-muted);
    line-height: 1.3;
  }

  .field-separator {
    border-top: 1px solid var(--border-color);
    padding-top: 12px;
    margin-top: 4px;
  }

  .separator-label {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
</style>
