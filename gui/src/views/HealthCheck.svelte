<script lang="ts">
  import { onMount } from 'svelte';
  import { loadSiteConfig } from '$lib/services/config';
  import {
    buildHealthChecks,
    runHealthCheck,
    type HealthCheckResult,
  } from '$lib/services/healthCheck';
  import type { SiteConfig } from '$lib/types';

  interface Props {
    siteName: string;
  }

  let { siteName }: Props = $props();

  let config = $state<SiteConfig | null>(null);
  let loadError = $state('');
  let checks = $state<HealthCheckResult[]>([]);
  let expandedChecks = $state<Set<number>>(new Set());
  let running = $state(false);

  let passedCount = $derived(checks.filter((c) => c.status === 'passed').length);
  let failedCount = $derived(checks.filter((c) => c.status === 'failed').length);
  let totalCount = $derived(checks.length);
  let hasResults = $derived(checks.some((c) => c.status === 'passed' || c.status === 'failed'));

  onMount(async () => {
    try {
      config = await loadSiteConfig(siteName);
      const definitions = buildHealthChecks(config);
      checks = definitions.map((d) => ({
        name: d.name,
        command: d.command,
        status: 'pending' as const,
      }));
    } catch (e) {
      loadError = `Failed to load site config: ${e}`;
    }
  });

  async function runAllChecks() {
    if (!config) return;
    running = true;

    const definitions = buildHealthChecks(config);
    // Reset all to pending
    checks = definitions.map((d) => ({
      name: d.name,
      command: d.command,
      status: 'pending' as const,
    }));

    // Run sequentially, showing results as they complete
    for (let i = 0; i < definitions.length; i++) {
      // Mark as running
      checks[i] = { ...checks[i], status: 'running' };
      checks = [...checks]; // trigger reactivity

      const result = await runHealthCheck(definitions[i].name, definitions[i].command);
      result.command = definitions[i].command;
      checks[i] = result;
      checks = [...checks]; // trigger reactivity
    }

    running = false;
  }

  async function rerunCheck(index: number) {
    if (!config) return;
    const definitions = buildHealthChecks(config);
    if (index < 0 || index >= definitions.length) return;

    checks[index] = { ...checks[index], status: 'running' };
    checks = [...checks];

    const result = await runHealthCheck(definitions[index].name, definitions[index].command);
    result.command = definitions[index].command;
    checks[index] = result;
    checks = [...checks];
  }

  function toggleExpanded(index: number) {
    const next = new Set(expandedChecks);
    if (next.has(index)) {
      next.delete(index);
    } else {
      next.add(index);
    }
    expandedChecks = next;
  }
</script>

<div class="view-container">
  <header class="view-header">
    <div class="header-content">
      <h2>Environment Health Check</h2>
      <p class="subtitle">
        Diagnostic checks for <strong>{siteName}</strong>
      </p>
    </div>

    <div class="header-actions">
      <button
        class="btn btn-primary"
        onclick={runAllChecks}
        disabled={running || !config}
      >
        {running ? 'Running...' : 'Run All Checks'}
      </button>
    </div>
  </header>

  {#if loadError}
    <div class="error-banner">
      <span class="error-icon">{'\u2717'}</span>
      <div>
        <strong>Configuration Error</strong>
        <p>{loadError}</p>
      </div>
    </div>
  {:else}
    <div class="checks-list">
      {#each checks as check, idx (idx)}
        <div class="check-row" class:expanded={expandedChecks.has(idx)}>
          <div class="check-main">
            <button
              class="check-expand-btn"
              onclick={() => toggleExpanded(idx)}
              disabled={check.status === 'pending' || check.status === 'running'}
            >
              <span class="status-indicator" class:pending={check.status === 'pending'} class:running={check.status === 'running'} class:passed={check.status === 'passed'} class:failed={check.status === 'failed'}>
                {#if check.status === 'pending'}
                  <span class="status-icon pending-icon">{'\u25CB'}</span>
                {:else if check.status === 'running'}
                  <span class="status-icon running-spinner"></span>
                {:else if check.status === 'passed'}
                  <span class="status-icon passed-icon">{'\u2713'}</span>
                {:else}
                  <span class="status-icon failed-icon">{'\u2717'}</span>
                {/if}
              </span>
            </button>

            <span class="check-name">{check.name}</span>

            <div class="check-actions">
              {#if check.status !== 'running'}
                <button
                  class="rerun-btn"
                  onclick={() => rerunCheck(idx)}
                  title="Re-run this check"
                  disabled={running}
                >
                  Re-run
                </button>
              {/if}
            </div>
          </div>

          {#if expandedChecks.has(idx) && (check.output || check.error || check.command)}
            <div class="check-detail">
              {#if check.command}
                <div class="detail-section">
                  <span class="detail-label">Command:</span>
                  <code class="detail-code">{check.command}</code>
                </div>
              {/if}
              {#if check.output}
                <div class="detail-section">
                  <span class="detail-label">Output:</span>
                  <pre class="detail-output">{check.output}</pre>
                </div>
              {/if}
              {#if check.error}
                <div class="detail-section">
                  <span class="detail-label">Error:</span>
                  <pre class="detail-output error-output">{check.error}</pre>
                </div>
              {/if}
            </div>
          {/if}
        </div>
      {/each}
    </div>

    {#if hasResults}
      <div class="summary-bar" class:all-passed={failedCount === 0} class:has-failures={failedCount > 0}>
        <span class="summary-text">
          {passedCount} of {totalCount} checks passed
          {#if failedCount > 0}
            &mdash; {failedCount} failed
          {/if}
        </span>
      </div>
    {/if}
  {/if}
</div>

<style>
  .view-container {
    padding: 32px;
    max-width: 800px;
  }

  .view-header {
    margin-bottom: 24px;
  }

  .header-content {
    margin-bottom: 16px;
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

  .header-actions {
    display: flex;
    gap: 8px;
  }

  /* Error banner */
  .error-banner {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 12px 14px;
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.3);
    border-radius: var(--radius-md);
    color: var(--error);
    font-size: 13px;
  }

  .error-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    border-radius: 50%;
    background: rgba(239, 68, 68, 0.2);
    font-weight: 700;
    flex-shrink: 0;
  }

  /* Check list */
  .checks-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .check-row {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    overflow: hidden;
    transition: border-color 0.15s ease;
  }

  .check-row.expanded {
    border-color: var(--text-muted);
  }

  .check-main {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 14px;
  }

  .check-expand-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    padding: 0;
  }

  .status-indicator {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
  }

  .status-icon {
    font-size: 16px;
    line-height: 1;
  }

  .pending-icon {
    color: var(--text-muted);
  }

  .passed-icon {
    color: var(--success);
    font-weight: 700;
  }

  .failed-icon {
    color: var(--error);
    font-weight: 700;
  }

  .running-spinner {
    display: inline-block;
    width: 16px;
    height: 16px;
    border: 2px solid var(--border-color);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .check-name {
    flex: 1;
    font-size: 13px;
    font-weight: 500;
    color: var(--text-primary);
  }

  .check-actions {
    flex-shrink: 0;
  }

  .rerun-btn {
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 600;
    color: var(--text-muted);
    border-radius: var(--radius-sm);
    transition: all 0.15s ease;
  }

  .rerun-btn:hover:not(:disabled) {
    background: var(--bg-hover);
    color: var(--text-primary);
  }

  /* Detail section */
  .check-detail {
    border-top: 1px solid var(--border-color);
    padding: 10px 14px;
    background: var(--bg-primary);
  }

  .detail-section {
    margin-bottom: 8px;
  }

  .detail-section:last-child {
    margin-bottom: 0;
  }

  .detail-label {
    display: block;
    font-size: 11px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 4px;
  }

  .detail-code {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--text-secondary);
    background: var(--bg-input);
    padding: 4px 8px;
    border-radius: var(--radius-sm);
    display: inline-block;
    word-break: break-all;
  }

  .detail-output {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--text-secondary);
    background: var(--bg-input);
    padding: 8px 10px;
    border-radius: var(--radius-sm);
    white-space: pre-wrap;
    word-break: break-all;
    max-height: 200px;
    overflow-y: auto;
    margin: 0;
  }

  .error-output {
    color: var(--error);
  }

  /* Summary */
  .summary-bar {
    margin-top: 16px;
    padding: 12px 16px;
    border-radius: var(--radius-md);
    font-size: 13px;
    font-weight: 500;
  }

  .summary-bar.all-passed {
    background: rgba(34, 197, 94, 0.1);
    border: 1px solid rgba(34, 197, 94, 0.3);
    color: var(--success);
  }

  .summary-bar.has-failures {
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.3);
    color: var(--error);
  }

  /* Buttons */
  .btn {
    padding: 8px 16px;
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

  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
</style>
