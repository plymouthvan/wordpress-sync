<script lang="ts">
  import { onMount } from 'svelte';
  import { settings } from '$lib/stores/settings';
  import { executeCommand } from '$lib/services/cli';
  import { getSiteConfigPath } from '$lib/services/config';
  import {
    parseCommandOutput,
    groupBySection,
    exportAsShellScript,
    type CommandEntry,
  } from '$lib/utils/commandParser';

  interface Props {
    siteName: string;
    direction?: 'push' | 'pull';
  }

  let { siteName, direction = 'pull' }: Props = $props();

  let loading = $state(true);
  let error = $state('');
  let entries = $state<CommandEntry[]>([]);
  let sections = $state<Map<string, CommandEntry[]>>(new Map());
  let collapsedSections = $state<Set<string>>(new Set());
  let copySuccess = $state(false);
  let rawOutput = $state('');

  // Default sections used when output is empty or parsing yields no results
  const DEFAULT_SECTIONS = [
    'Environment Validation',
    'Directory Setup',
    'Pre-sync Cleanup',
    'Maintenance Mode',
    'Database Operations',
    'File Transfer',
    'URL Replacement',
    'Plugin Management',
    'Validation',
    'Maintenance Mode Off',
    'Backup Management',
    'Cleanup',
  ];

  onMount(async () => {
    await loadCommands();
  });

  async function loadCommands() {
    loading = true;
    error = '';

    const cliPath = $settings.cli_path;
    if (!cliPath) {
      error = 'CLI path not configured. Please set it in Settings.';
      loading = false;
      return;
    }

    try {
      const configPath = await getSiteConfigPath(siteName);
      const result = await executeCommand(
        `"${cliPath}" --config "${configPath}" --command-only`
      );

      rawOutput = result.stdout + (result.stderr ? '\n' + result.stderr : '');

      if (result.code !== 0 && !result.stdout) {
        error = result.stderr || 'Command preview failed with no output.';
        loading = false;
        return;
      }

      entries = parseCommandOutput(result.stdout);
      sections = groupBySection(entries);
    } catch (e) {
      error = String(e);
    }

    loading = false;
  }

  function toggleSection(section: string) {
    const next = new Set(collapsedSections);
    if (next.has(section)) {
      next.delete(section);
    } else {
      next.add(section);
    }
    collapsedSections = next;
  }

  function expandAll() {
    collapsedSections = new Set();
  }

  function collapseAll() {
    collapsedSections = new Set(sections.keys());
  }

  async function copyAllCommands() {
    const script = exportAsShellScript(entries);
    try {
      await navigator.clipboard.writeText(script);
      copySuccess = true;
      setTimeout(() => { copySuccess = false; }, 2000);
    } catch {
      // Fallback: ignore
    }
  }

  async function copySingleCommand(command: string) {
    try {
      await navigator.clipboard.writeText(command);
    } catch {
      // Fallback: ignore
    }
  }
</script>

<div class="view-container">
  <header class="view-header">
    <div class="header-content">
      <h2>Command Preview</h2>
      <p class="subtitle">
        Commands that would be executed for a
        <strong>{direction}</strong> sync on <strong>{siteName}</strong>
      </p>
    </div>

    {#if !loading && entries.length > 0}
      <div class="header-actions">
        <button class="btn btn-ghost" onclick={expandAll}>Expand All</button>
        <button class="btn btn-ghost" onclick={collapseAll}>Collapse All</button>
        <button class="btn btn-secondary" onclick={copyAllCommands}>
          {copySuccess ? 'Copied!' : 'Copy All Commands'}
        </button>
      </div>
    {/if}
  </header>

  {#if loading}
    <div class="loading-state">
      <div class="spinner"></div>
      <p>Loading command preview...</p>
    </div>
  {:else if error}
    <div class="error-banner">
      <span class="error-icon">{'\u2717'}</span>
      <div>
        <strong>Failed to load command preview</strong>
        <p>{error}</p>
      </div>
    </div>
  {:else if entries.length === 0}
    <div class="empty-state">
      <p>No commands generated. The CLI may not support --command-only, or there are no commands for this configuration.</p>
      {#if rawOutput}
        <details class="raw-output">
          <summary>Raw output</summary>
          <pre>{rawOutput}</pre>
        </details>
      {/if}
    </div>
  {:else}
    <div class="sections-list">
      {#each [...sections.entries()] as [sectionName, sectionEntries] (sectionName)}
        {@const isCollapsed = collapsedSections.has(sectionName)}
        <div class="section-panel">
          <button
            class="section-header"
            onclick={() => toggleSection(sectionName)}
          >
            <span class="section-chevron" class:collapsed={isCollapsed}>
              {'\u25B6'}
            </span>
            <span class="section-title">{sectionName}</span>
            <span class="section-count">{sectionEntries.length} command{sectionEntries.length !== 1 ? 's' : ''}</span>
          </button>

          {#if !isCollapsed}
            <div class="section-body">
              {#each sectionEntries as entry, idx (idx)}
                <div class="command-entry">
                  <div class="command-meta">
                    <span
                      class="env-badge"
                      class:local={entry.environment === 'local'}
                      class:remote={entry.environment === 'remote'}
                      class:both={entry.environment === 'both'}
                    >
                      {#if entry.environment === 'local'}
                        LOCAL
                      {:else if entry.environment === 'remote'}
                        REMOTE
                      {:else}
                        BOTH
                      {/if}
                    </span>
                    {#if entry.user}
                      <span class="user-badge">{entry.user}</span>
                    {/if}
                    {#if entry.description}
                      <span class="command-desc">{entry.description}</span>
                    {/if}
                  </div>
                  <div class="command-line-wrapper">
                    <code class="command-line">{entry.command}</code>
                    <button
                      class="copy-btn"
                      onclick={() => copySingleCommand(entry.command)}
                      title="Copy command"
                    >
                      <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
                        <path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 0 1 0 1.5h-1.5a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-1.5a.75.75 0 0 1 1.5 0v1.5A1.75 1.75 0 0 1 9.25 16h-7.5A1.75 1.75 0 0 1 0 14.25Z" />
                        <path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0 1 14.25 11h-7.5A1.75 1.75 0 0 1 5 9.25Zm1.75-.25a.25.25 0 0 0-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 0 0 .25-.25v-7.5a.25.25 0 0 0-.25-.25Z" />
                      </svg>
                    </button>
                  </div>
                </div>
              {/each}
            </div>
          {/if}
        </div>
      {/each}
    </div>

    <div class="summary-bar">
      <span class="summary-text">
        {entries.length} command{entries.length !== 1 ? 's' : ''} across {sections.size} section{sections.size !== 1 ? 's' : ''}
      </span>
    </div>
  {/if}
</div>

<style>
  .view-container {
    padding: 32px;
    max-width: 960px;
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
    align-items: center;
  }

  /* Loading */
  .loading-state {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 40px 16px;
    color: var(--text-secondary);
    font-size: 14px;
  }

  .spinner {
    width: 20px;
    height: 20px;
    border: 2px solid var(--border-color);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  /* Error */
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

  /* Empty state */
  .empty-state {
    padding: 40px 20px;
    text-align: center;
    color: var(--text-muted);
    font-size: 14px;
  }

  .raw-output {
    margin-top: 16px;
    text-align: left;
  }

  .raw-output summary {
    cursor: pointer;
    color: var(--text-secondary);
    font-size: 13px;
  }

  .raw-output pre {
    margin-top: 8px;
    padding: 12px;
    background: var(--bg-input);
    border-radius: var(--radius-sm);
    font-family: var(--font-mono);
    font-size: 12px;
    white-space: pre-wrap;
    word-break: break-all;
    max-height: 300px;
    overflow-y: auto;
  }

  /* Sections */
  .sections-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .section-panel {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    overflow: hidden;
  }

  .section-header {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    padding: 12px 16px;
    text-align: left;
    color: var(--text-primary);
    font-size: 14px;
    font-weight: 600;
    transition: background 0.1s ease;
  }

  .section-header:hover {
    background: var(--bg-hover);
  }

  .section-chevron {
    display: inline-block;
    font-size: 10px;
    transition: transform 0.15s ease;
    transform: rotate(90deg);
    color: var(--text-muted);
  }

  .section-chevron.collapsed {
    transform: rotate(0deg);
  }

  .section-title {
    flex: 1;
  }

  .section-count {
    font-size: 12px;
    font-weight: 400;
    color: var(--text-muted);
  }

  .section-body {
    border-top: 1px solid var(--border-color);
    padding: 8px 0;
  }

  /* Command entries */
  .command-entry {
    padding: 8px 16px;
    transition: background 0.1s ease;
  }

  .command-entry:hover {
    background: var(--bg-hover);
  }

  .command-entry:hover .copy-btn {
    opacity: 1;
  }

  .command-meta {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 4px;
    flex-wrap: wrap;
  }

  .env-badge {
    padding: 1px 6px;
    border-radius: 3px;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .env-badge.local {
    background: rgba(59, 130, 246, 0.15);
    color: var(--accent);
  }

  .env-badge.remote {
    background: rgba(249, 115, 22, 0.15);
    color: #f97316;
  }

  .env-badge.both {
    background: rgba(139, 92, 246, 0.15);
    color: #8b5cf6;
  }

  .user-badge {
    padding: 1px 6px;
    border-radius: 3px;
    font-size: 10px;
    font-weight: 600;
    background: var(--bg-hover);
    color: var(--text-secondary);
    font-family: var(--font-mono);
  }

  .command-desc {
    font-size: 12px;
    color: var(--text-muted);
    font-style: italic;
  }

  .command-line-wrapper {
    display: flex;
    align-items: flex-start;
    gap: 8px;
  }

  .command-line {
    flex: 1;
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--text-primary);
    background: var(--bg-input);
    padding: 6px 10px;
    border-radius: var(--radius-sm);
    user-select: text;
    word-break: break-all;
    white-space: pre-wrap;
  }

  .copy-btn {
    flex-shrink: 0;
    padding: 6px;
    border-radius: var(--radius-sm);
    color: var(--text-muted);
    opacity: 0;
    transition: all 0.15s ease;
  }

  .copy-btn:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
  }

  /* Summary bar */
  .summary-bar {
    margin-top: 16px;
    padding: 12px 16px;
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
  }

  .summary-text {
    font-size: 13px;
    color: var(--text-secondary);
  }

  /* Buttons */
  .btn {
    padding: 6px 14px;
    font-size: 13px;
    font-weight: 500;
    border-radius: var(--radius-sm);
    transition: all 0.15s ease;
  }

  .btn-ghost {
    color: var(--text-secondary);
    background: transparent;
  }

  .btn-ghost:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
  }

  .btn-secondary {
    background: var(--bg-hover);
    color: var(--text-primary);
    border: 1px solid var(--border-color);
  }

  .btn-secondary:hover {
    background: var(--border-color);
  }
</style>
