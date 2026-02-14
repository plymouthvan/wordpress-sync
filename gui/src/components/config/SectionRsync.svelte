<script lang="ts">
  import type { SiteConfig } from '$lib/types';
  import TagInput from '../TagInput.svelte';

  interface Props {
    config: SiteConfig;
    onchange: (config: SiteConfig) => void;
  }

  let { config, onchange }: Props = $props();

  function updateBool(key: 'dry_run' | 'delete' | 'progress' | 'verbose' | 'compress', value: boolean) {
    onchange({ ...config, rsync: { ...config.rsync, [key]: value } });
  }

  function updateString(key: 'chmod_files' | 'chmod_dirs', value: string) {
    onchange({ ...config, rsync: { ...config.rsync, [key]: value } });
  }

  function updateExcludes(tags: string[]) {
    onchange({ ...config, rsync: { ...config.rsync, excludes: tags } });
  }

  function updateCleanupFiles(tags: string[]) {
    onchange({ ...config, rsync: { ...config.rsync, cleanup_files: tags } });
  }
</script>

<div class="form-layout">
  <div class="toggles-grid">
    <label class="toggle-field">
      <span class="toggle-label">Dry Run by Default</span>
      <input
        type="checkbox"
        class="toggle-switch"
        checked={config.rsync.dry_run}
        onchange={(e) => updateBool('dry_run', e.currentTarget.checked)}
      />
    </label>

    <label class="toggle-field">
      <span class="toggle-label">Delete Extra Files</span>
      <input
        type="checkbox"
        class="toggle-switch"
        checked={config.rsync.delete}
        onchange={(e) => updateBool('delete', e.currentTarget.checked)}
      />
    </label>

    <label class="toggle-field">
      <span class="toggle-label">Show Progress</span>
      <input
        type="checkbox"
        class="toggle-switch"
        checked={config.rsync.progress}
        onchange={(e) => updateBool('progress', e.currentTarget.checked)}
      />
    </label>

    <label class="toggle-field">
      <span class="toggle-label">Verbose Output</span>
      <input
        type="checkbox"
        class="toggle-switch"
        checked={config.rsync.verbose}
        onchange={(e) => updateBool('verbose', e.currentTarget.checked)}
      />
    </label>

    <label class="toggle-field">
      <span class="toggle-label">Compress Transfer</span>
      <input
        type="checkbox"
        class="toggle-switch"
        checked={config.rsync.compress}
        onchange={(e) => updateBool('compress', e.currentTarget.checked)}
      />
    </label>
  </div>

  <div class="form-grid">
    <div class="field">
      <label for="chmod-files">File Permissions</label>
      <input
        id="chmod-files"
        type="text"
        value={config.rsync.chmod_files}
        oninput={(e) => updateString('chmod_files', e.currentTarget.value)}
        placeholder="644"
      />
    </div>

    <div class="field">
      <label for="chmod-dirs">Directory Permissions</label>
      <input
        id="chmod-dirs"
        type="text"
        value={config.rsync.chmod_dirs}
        oninput={(e) => updateString('chmod_dirs', e.currentTarget.value)}
        placeholder="755"
      />
    </div>

    <div class="field full-width">
      <label>Exclude Patterns</label>
      <TagInput
        tags={config.rsync.excludes}
        placeholder="Add exclude pattern..."
        onchange={updateExcludes}
      />
    </div>

    <div class="field full-width">
      <label>Cleanup Files</label>
      <TagInput
        tags={config.rsync.cleanup_files}
        placeholder="Add cleanup file pattern..."
        onchange={updateCleanupFiles}
      />
    </div>
  </div>
</div>

<style>
  .form-layout {
    display: flex;
    flex-direction: column;
    gap: 20px;
    padding-top: 12px;
  }

  .toggles-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
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

  .field input[type='text'] {
    width: 100%;
  }
</style>
