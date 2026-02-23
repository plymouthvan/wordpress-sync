<script lang="ts">
  import { open } from '@tauri-apps/plugin-dialog';
  import type { SiteConfig } from '$lib/types';
  import { termExec, termInfo, terminalOpen } from '$lib/stores/terminal';

  interface Props {
    config: SiteConfig;
    onchange: (config: SiteConfig) => void;
  }

  let { config, onchange }: Props = $props();
  let validating = $state(false);
  let validateResult = $state<'idle' | 'success' | 'error'>('idle');

  function update(key: 'local' | 'live' | 'db_filename', value: string) {
    onchange({ ...config, paths: { ...config.paths, [key]: value } });
  }

  // Extract local/remote db_temp (handles both new and legacy formats)
  let localDbTemp = $derived(
    typeof config.paths.db_temp === 'object' && config.paths.db_temp !== null
      ? config.paths.db_temp.local
      : (typeof config.paths.db_temp === 'string' ? config.paths.db_temp : '')
  );
  let remoteDbTemp = $derived(
    typeof config.paths.db_temp === 'object' && config.paths.db_temp !== null
      ? config.paths.db_temp.remote
      : (typeof config.paths.db_temp === 'string' ? config.paths.db_temp : '')
  );

  function updateLocalDbTemp(value: string) {
    const current = config.paths.db_temp;
    const remote = typeof current === 'object' && current !== null
      ? current.remote
      : (typeof current === 'string' ? current : '/tmp');

    onchange({
      ...config,
      paths: {
        ...config.paths,
        db_temp: { local: value, remote },
      }
    });
  }

  function updateRemoteDbTemp(value: string) {
    const current = config.paths.db_temp;
    const local = typeof current === 'object' && current !== null
      ? current.local
      : (typeof current === 'string' ? current : '/tmp');

    onchange({
      ...config,
      paths: {
        ...config.paths,
        db_temp: { local, remote: value },
      }
    });
  }

  async function browseLocalPath() {
    const selected = await open({
      multiple: false,
      title: 'Select Local WordPress Directory',
      directory: true
    });
    if (selected) {
      update('local', selected as string);
    }
  }

  async function browseLocalDbTemp() {
    const selected = await open({
      multiple: false,
      title: 'Select Local DB Temp Directory',
      directory: true
    });
    if (selected) {
      updateLocalDbTemp(selected as string);
    }
  }

  async function validatePaths() {
    const localPath = config.paths.local;
    if (!localPath) {
      termInfo('Local path is required for validation.');
      terminalOpen.set(true);
      return;
    }

    validating = true;
    validateResult = 'idle';
    terminalOpen.set(true);

    // Check local path exists and contains wp-config.php
    const cmd = `test -d "${localPath}" && test -f "${localPath}/wp-config.php" && echo "Valid WordPress installation at ${localPath}" || echo "Not a valid WordPress directory: ${localPath}"`;
    const display = `validate "${localPath}" (check directory + wp-config.php)`;

    const result = await termExec(display, cmd);
    validateResult = result.code === 0 ? 'success' : 'error';
    validating = false;

    setTimeout(() => { validateResult = 'idle'; }, 5000);
  }
</script>

<div class="form-layout">
  <!-- WordPress Paths -->
  <div class="section-group">
    <span class="group-label">WordPress Directories</span>

    <div class="field full-width">
      <label for="paths-local">Local WordPress Path</label>
      <div class="input-with-button">
        <input
          id="paths-local"
          type="text"
          value={config.paths.local}
          oninput={(e) => update('local', e.currentTarget.value)}
          placeholder="/var/www/html"
        />
        <button type="button" class="btn-browse" onclick={browseLocalPath}>Browse</button>
      </div>
    </div>

    <div class="field full-width">
      <label for="paths-live">Remote (Live) WordPress Path</label>
      <input
        id="paths-live"
        type="text"
        value={config.paths.live}
        oninput={(e) => update('live', e.currentTarget.value)}
        placeholder="/var/www/html"
      />
    </div>
  </div>

  <!-- DB Temp Directories -->
  <div class="section-group">
    <div class="group-header">
      <span class="group-label">Database Temp Directories</span>
      <span class="group-hint">Staging area for DB export/import. Relative paths resolve against each site's root.</span>
    </div>

    <div class="form-grid">
      <div class="field">
        <label for="paths-db-temp-local">Local DB Temp</label>
        <div class="input-with-button">
          <input
            id="paths-db-temp-local"
            type="text"
            value={localDbTemp}
            oninput={(e) => updateLocalDbTemp(e.currentTarget.value)}
            placeholder="/tmp"
          />
          <button type="button" class="btn-browse" onclick={browseLocalDbTemp}>Browse</button>
        </div>
      </div>

      <div class="field">
        <label for="paths-db-temp-remote">Remote DB Temp</label>
        <input
          id="paths-db-temp-remote"
          type="text"
          value={remoteDbTemp}
          oninput={(e) => updateRemoteDbTemp(e.currentTarget.value)}
          placeholder="/tmp"
        />
      </div>
    </div>
  </div>

  <!-- DB Filename -->
  <div class="section-group">
    <div class="form-grid">
      <div class="field">
        <label for="paths-db-filename">DB Export Filename</label>
        <input
          id="paths-db-filename"
          type="text"
          value={config.paths.db_filename}
          oninput={(e) => update('db_filename', e.currentTarget.value)}
          placeholder="database.sql"
        />
        <span class="field-hint">Name of the SQL dump file used during sync. Same name is used on both local and remote.</span>
      </div>
    </div>
  </div>

  <!-- Validate -->
  <div class="field full-width action-row">
    <button type="button" class="btn-action" onclick={validatePaths} disabled={validating}>
      {#if validating}
        Validating...
      {:else}
        Validate Paths
      {/if}
    </button>
    {#if validateResult === 'success'}
      <span class="result-badge success">Valid</span>
    {:else if validateResult === 'error'}
      <span class="result-badge error">Invalid</span>
    {/if}
  </div>
</div>

<style>
  .form-layout {
    display: flex;
    flex-direction: column;
    gap: 20px;
    padding-top: 12px;
  }

  .section-group {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .group-header {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .group-label {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .group-hint {
    font-size: 11px;
    color: var(--text-muted);
    line-height: 1.4;
  }

  .form-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
  }

  .full-width {
    grid-column: 1 / -1;
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

  .field input {
    width: 100%;
  }

  .field-hint {
    font-size: 11px;
    color: var(--text-muted);
    line-height: 1.3;
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

  .btn-action {
    padding: 8px 20px;
    background: var(--accent);
    color: #fff;
    border-radius: var(--radius-sm);
    font-size: 13px;
    font-weight: 600;
    transition: background 0.15s ease;
    width: auto;
    align-self: flex-start;
  }

  .btn-action:hover:not(:disabled) {
    background: var(--accent-hover);
  }

  .btn-action:disabled {
    opacity: 0.6;
    cursor: wait;
  }

  .action-row {
    flex-direction: row !important;
    align-items: center;
    gap: 12px !important;
  }

  .result-badge {
    font-size: 12px;
    font-weight: 600;
    padding: 4px 12px;
    border-radius: var(--radius-sm);
  }

  .result-badge.success {
    color: var(--success);
    background: rgba(34, 197, 94, 0.1);
  }

  .result-badge.error {
    color: var(--error);
    background: rgba(239, 68, 68, 0.1);
  }
</style>
