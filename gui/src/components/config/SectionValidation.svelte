<script lang="ts">
  import type { SiteConfig } from '$lib/types';
  import TagInput from '../TagInput.svelte';

  interface Props {
    config: SiteConfig;
    onchange: (config: SiteConfig) => void;
  }

  let { config, onchange }: Props = $props();

  function updateEnabled(value: boolean) {
    onchange({ ...config, validation: { ...config.validation, enabled: value } });
  }

  function updateCoreFiles(key: 'verify_checksums', value: boolean) {
    onchange({
      ...config,
      validation: {
        ...config.validation,
        checks: {
          ...config.validation.checks,
          core_files: { ...config.validation.checks.core_files, [key]: value }
        }
      }
    });
  }

  function updateCriticalFiles(tags: string[]) {
    onchange({
      ...config,
      validation: {
        ...config.validation,
        checks: {
          ...config.validation.checks,
          core_files: { ...config.validation.checks.core_files, critical_files: tags }
        }
      }
    });
  }

  function updateDatabase(key: 'verify_core_tables', value: boolean) {
    onchange({
      ...config,
      validation: {
        ...config.validation,
        checks: {
          ...config.validation.checks,
          database: { ...config.validation.checks.database, [key]: value }
        }
      }
    });
  }

  function updateAdditionalTables(tags: string[]) {
    onchange({
      ...config,
      validation: {
        ...config.validation,
        checks: {
          ...config.validation.checks,
          database: { ...config.validation.checks.database, additional_tables: tags }
        }
      }
    });
  }

  function updateAccessibility(key: 'homepage' | 'wp_admin', value: boolean) {
    onchange({
      ...config,
      validation: {
        ...config.validation,
        checks: {
          ...config.validation.checks,
          accessibility: { ...config.validation.checks.accessibility, [key]: value }
        }
      }
    });
  }
</script>

<div class="form-layout">
  <div class="toggles-row single">
    <label class="toggle-field">
      <span class="toggle-label">Enable Validation</span>
      <input
        type="checkbox"
        class="toggle-switch"
        checked={config.validation.enabled}
        onchange={(e) => updateEnabled(e.currentTarget.checked)}
      />
    </label>
  </div>

  <div class="field-separator">
    <span class="separator-label">Core Files</span>
  </div>

  <div class="toggles-row single">
    <label class="toggle-field">
      <span class="toggle-label">Verify Core Checksums</span>
      <input
        type="checkbox"
        class="toggle-switch"
        checked={config.validation.checks.core_files.verify_checksums}
        onchange={(e) => updateCoreFiles('verify_checksums', e.currentTarget.checked)}
      />
    </label>
  </div>

  <div class="field full-width">
    <label>Critical Files</label>
    <TagInput
      tags={config.validation.checks.core_files.critical_files}
      placeholder="Add critical file path..."
      onchange={updateCriticalFiles}
    />
  </div>

  <div class="field-separator">
    <span class="separator-label">Database</span>
  </div>

  <div class="toggles-row single">
    <label class="toggle-field">
      <span class="toggle-label">Verify Core DB Tables</span>
      <input
        type="checkbox"
        class="toggle-switch"
        checked={config.validation.checks.database.verify_core_tables}
        onchange={(e) => updateDatabase('verify_core_tables', e.currentTarget.checked)}
      />
    </label>
  </div>

  <div class="field full-width">
    <label>Additional Tables</label>
    <TagInput
      tags={config.validation.checks.database.additional_tables}
      placeholder="Add table name..."
      onchange={updateAdditionalTables}
    />
  </div>

  <div class="field-separator">
    <span class="separator-label">Accessibility</span>
  </div>

  <div class="toggles-row">
    <label class="toggle-field">
      <span class="toggle-label">Check Homepage</span>
      <input
        type="checkbox"
        class="toggle-switch"
        checked={config.validation.checks.accessibility.homepage}
        onchange={(e) => updateAccessibility('homepage', e.currentTarget.checked)}
      />
    </label>

    <label class="toggle-field">
      <span class="toggle-label">Check WP Admin</span>
      <input
        type="checkbox"
        class="toggle-switch"
        checked={config.validation.checks.accessibility.wp_admin}
        onchange={(e) => updateAccessibility('wp_admin', e.currentTarget.checked)}
      />
    </label>
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

  .field {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .full-width {
    width: 100%;
  }

  .field label {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.03em;
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
