<script lang="ts">
  import type { SiteConfig } from '$lib/types';

  interface Props {
    config: SiteConfig;
    onchange: (config: SiteConfig) => void;
  }

  let { config, onchange }: Props = $props();

  function updateTop(key: 'enabled' | 'cleanup_prompt', value: boolean) {
    onchange({ ...config, backup: { ...config.backup, [key]: value } });
  }

  function updateTopString(key: 'directory' | 'archive_format', value: string) {
    onchange({ ...config, backup: { ...config.backup, [key]: value } });
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

  function updateDbString(key: 'directory' | 'filename_format', value: string) {
    onchange({
      ...config,
      backup: {
        ...config.backup,
        database: { ...config.backup.database, [key]: value }
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

  <div class="form-grid">
    <div class="field">
      <label for="backup-dir">Backup Directory</label>
      <input
        id="backup-dir"
        type="text"
        value={config.backup.directory}
        oninput={(e) => updateTopString('directory', e.currentTarget.value)}
        placeholder="backups/"
      />
    </div>

    <div class="field">
      <label for="backup-archive">Archive Name Format</label>
      <input
        id="backup-archive"
        type="text"
        value={config.backup.archive_format}
        oninput={(e) => updateTopString('archive_format', e.currentTarget.value)}
        placeholder="backup-%Y%m%d-%H%M%S.tar.gz"
      />
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
      <label for="db-backup-dir">DB Backup Directory</label>
      <input
        id="db-backup-dir"
        type="text"
        value={config.backup.database.directory}
        oninput={(e) => updateDbString('directory', e.currentTarget.value)}
        placeholder="db-backups/"
      />
    </div>

    <div class="field">
      <label for="db-backup-filename">DB Backup Filename Format</label>
      <input
        id="db-backup-filename"
        type="text"
        value={config.backup.database.filename_format}
        oninput={(e) => updateDbString('filename_format', e.currentTarget.value)}
        placeholder="db-%Y%m%d-%H%M%S.sql"
      />
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
