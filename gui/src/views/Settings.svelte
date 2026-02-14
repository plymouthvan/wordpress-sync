<script lang="ts">
  import { settings, persistSettings } from '$lib/stores/settings';
  import type { PrerequisiteCheck, AppSettings } from '$lib/types';
  import type { Theme } from '$lib/utils/theme';
  import { onMount } from 'svelte';

  let prerequisites: PrerequisiteCheck[] = $state([]);
  let checking = $state(false);

  const isMac = typeof navigator !== 'undefined' && navigator.platform.includes('Mac');

  onMount(async () => {
    await checkPrereqs();
  });

  async function checkPrereqs() {
    checking = true;
    try {
      const { checkAllPrerequisites } = await import('$lib/services/prerequisites');
      prerequisites = await checkAllPrerequisites();
    } catch (e) {
      console.error('Failed to check prerequisites:', e);
    } finally {
      checking = false;
    }
  }

  async function handleThemeChange(event: Event) {
    const target = event.target as HTMLSelectElement;
    const newTheme = target.value as Theme;
    const updated: AppSettings = { ...$settings, theme: newTheme };
    await persistSettings(updated);
  }
</script>

<div class="view-container">
  <header class="view-header">
    <h2>Settings</h2>
    <p class="subtitle">Global application configuration and prerequisites</p>
  </header>

  <section class="settings-section">
    <h3>Prerequisites</h3>
    <p class="section-desc">Required tools for WordPress sync operations</p>

    {#if checking}
      <div class="checking-status">Checking prerequisites...</div>
    {:else}
      <div class="prereq-list">
        {#each prerequisites as check (check.name)}
          <div class="prereq-item">
            <div class="prereq-status" class:found={check.found} class:missing={!check.found}>
              {check.found ? 'OK' : 'Missing'}
            </div>
            <div class="prereq-info">
              <span class="prereq-name">{check.name}</span>
              {#if check.path}
                <span class="prereq-path">{check.path}</span>
              {/if}
              {#if check.error}
                <span class="prereq-error">{check.error}</span>
              {/if}
            </div>
          </div>
        {:else}
          <p class="empty-state">Click "Re-check" to scan for prerequisites.</p>
        {/each}
      </div>
      <button class="btn btn-secondary" onclick={checkPrereqs}>Re-check</button>
    {/if}
  </section>

  <section class="settings-section">
    <h3>Application</h3>
    <p class="section-desc">General application settings</p>

    <div class="settings-grid">
      <div class="setting-row">
        <label class="setting-label" for="cli-path">CLI Path</label>
        <input
          id="cli-path"
          type="text"
          value={$settings.cli_path || '(auto-detect)'}
          readonly
          class="setting-input"
        />
      </div>
      <div class="setting-row">
        <label class="setting-label" for="theme">Theme</label>
        <select id="theme" class="setting-input" value={$settings.theme} onchange={handleThemeChange}>
          <option value="system">System</option>
          <option value="light">Light</option>
          <option value="dark">Dark</option>
        </select>
      </div>
      <div class="setting-row">
        <label class="setting-label" for="log-retention">Log Retention (days)</label>
        <input
          id="log-retention"
          type="number"
          value={$settings.log_retention_days}
          readonly
          class="setting-input"
        />
      </div>
    </div>
    <p class="coming-soon-inline">Additional settings coming soon</p>
  </section>

  <section class="settings-section">
    <h3>Keyboard Shortcuts</h3>
    <p class="section-desc">Available keyboard shortcuts</p>

    <div class="shortcuts-list">
      <div class="shortcut-row">
        <kbd class="shortcut-key">{isMac ? '\u2318' : 'Ctrl+'}N</kbd>
        <span class="shortcut-desc">Add new site</span>
      </div>
      <div class="shortcut-row">
        <kbd class="shortcut-key">{isMac ? '\u2318' : 'Ctrl+'}S</kbd>
        <span class="shortcut-desc">Save current config</span>
      </div>
      <div class="shortcut-row">
        <kbd class="shortcut-key">{isMac ? '\u2318' : 'Ctrl+'},</kbd>
        <span class="shortcut-desc">Open Settings</span>
      </div>
      <div class="shortcut-row">
        <kbd class="shortcut-key">{isMac ? '\u2318' : 'Ctrl+'}K</kbd>
        <span class="shortcut-desc">Focus site search</span>
      </div>
    </div>
  </section>
</div>

<style>
  .view-container {
    padding: 32px;
    max-width: 700px;
  }

  .view-header {
    margin-bottom: 32px;
  }

  .view-header h2 {
    font-size: 24px;
    font-weight: 600;
    margin-bottom: 4px;
  }

  .subtitle {
    color: var(--text-secondary);
    font-size: 14px;
  }

  .settings-section {
    margin-bottom: 32px;
    padding: 24px;
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
  }

  .settings-section h3 {
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 4px;
  }

  .section-desc {
    color: var(--text-muted);
    font-size: 13px;
    margin-bottom: 16px;
  }

  .checking-status {
    padding: 12px;
    color: var(--text-secondary);
    font-size: 13px;
  }

  .prereq-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 16px;
  }

  .prereq-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 12px;
    background: var(--bg-primary);
    border-radius: var(--radius-sm);
  }

  .prereq-status {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 2px 8px;
    border-radius: var(--radius-sm);
  }

  .prereq-status.found {
    color: var(--success);
    background: rgba(34, 197, 94, 0.1);
  }

  .prereq-status.missing {
    color: var(--error);
    background: rgba(239, 68, 68, 0.1);
  }

  .prereq-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .prereq-name {
    font-size: 13px;
    font-weight: 500;
  }

  .prereq-path {
    font-size: 12px;
    color: var(--text-muted);
    font-family: var(--font-mono);
  }

  .prereq-error {
    font-size: 12px;
    color: var(--error);
  }

  .empty-state {
    color: var(--text-muted);
    font-size: 13px;
    padding: 8px 0;
  }

  .btn {
    padding: 8px 16px;
    border-radius: var(--radius-sm);
    font-size: 13px;
    font-weight: 500;
    transition: all 0.15s ease;
  }

  .btn-secondary {
    background: var(--bg-hover);
    color: var(--text-primary);
    border: 1px solid var(--border-color);
  }

  .btn-secondary:hover {
    background: var(--border-color);
  }

  .settings-grid {
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin-bottom: 16px;
  }

  .setting-row {
    display: flex;
    align-items: center;
    gap: 16px;
  }

  .setting-label {
    flex-shrink: 0;
    width: 160px;
    font-size: 13px;
    font-weight: 500;
    color: var(--text-secondary);
  }

  .setting-input {
    flex: 1;
    font-size: 13px;
  }

  .coming-soon-inline {
    font-size: 12px;
    color: var(--accent);
    font-style: italic;
  }

  .shortcuts-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .shortcut-row {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 6px 12px;
    background: var(--bg-primary);
    border-radius: var(--radius-sm);
  }

  .shortcut-key {
    display: inline-block;
    min-width: 80px;
    padding: 3px 8px;
    background: var(--bg-input);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    font-family: var(--font-mono);
    font-size: 12px;
    font-weight: 600;
    color: var(--text-primary);
    text-align: center;
  }

  .shortcut-desc {
    font-size: 13px;
    color: var(--text-secondary);
  }
</style>
