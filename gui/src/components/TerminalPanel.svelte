<script lang="ts">
  import { terminalLines, terminalOpen, terminalUnread, terminalBusy, termClear, termMarkRead } from '$lib/stores/terminal';
  import { onDestroy } from 'svelte';

  let scrollContainer: HTMLDivElement | undefined = $state(undefined);
  let autoScroll = $state(true);
  let lines = $state<typeof $terminalLines>([]);
  let isOpen = $state(false);
  let unread = $state(0);
  let busy = $state(false);

  const unsubLines = terminalLines.subscribe((v) => { lines = v; });
  const unsubOpen = terminalOpen.subscribe((v) => { isOpen = v; });
  const unsubUnread = terminalUnread.subscribe((v) => { unread = v; });
  const unsubBusy = terminalBusy.subscribe((v) => { busy = v; });

  onDestroy(() => {
    unsubLines();
    unsubOpen();
    unsubUnread();
    unsubBusy();
  });

  function toggle() {
    const next = !isOpen;
    terminalOpen.set(next);
    if (next) {
      termMarkRead();
    }
  }

  function clear() {
    termClear();
  }

  function formatTime(d: Date): string {
    return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }

  // Auto-scroll when new lines arrive
  $effect(() => {
    const _len = lines.length;
    if (autoScroll && scrollContainer) {
      requestAnimationFrame(() => {
        if (scrollContainer) {
          scrollContainer.scrollTop = scrollContainer.scrollHeight;
        }
      });
    }
  });

  function handleScroll() {
    if (!scrollContainer) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollContainer;
    // If user scrolled up more than 40px from bottom, pause auto-scroll
    autoScroll = scrollHeight - scrollTop - clientHeight < 40;
  }
</script>

<div class="terminal-panel" class:open={isOpen}>
  <button class="terminal-tab" onclick={toggle} type="button">
    <span class="tab-label">
      <span class="tab-icon">&#9654;</span>
      Terminal
    </span>
    {#if busy}
      <span class="spinner"></span>
    {/if}
    {#if unread > 0 && !isOpen}
      <span class="badge">{unread > 99 ? '99+' : unread}</span>
    {/if}
    <span class="chevron" class:open={isOpen}>&#x25B2;</span>
  </button>

  {#if isOpen}
    <div class="terminal-toolbar">
      <div class="toolbar-left">
        <span class="line-count">{lines.length} line{lines.length !== 1 ? 's' : ''}</span>
      </div>
      <div class="toolbar-right">
        <label class="auto-scroll-toggle">
          <input type="checkbox" bind:checked={autoScroll} />
          Auto-scroll
        </label>
        <button class="toolbar-btn" onclick={clear} type="button">Clear</button>
      </div>
    </div>
    <div
      class="terminal-body"
      bind:this={scrollContainer}
      onscroll={handleScroll}
    >
      {#if lines.length === 0}
        <div class="empty-state">No output yet. Actions and commands will appear here.</div>
      {:else}
        {#each lines as line (line.id)}
          <div class="term-line {line.type}">
            <span class="term-time">{formatTime(line.timestamp)}</span>
            {#if line.type === 'command'}
              <span class="term-prefix">$</span>
              <span class="term-text">{line.text}</span>
            {:else if line.type === 'stderr'}
              <span class="term-prefix">!</span>
              <span class="term-text">{line.text}</span>
            {:else if line.type === 'error'}
              <span class="term-prefix">x</span>
              <span class="term-text">{line.text}</span>
            {:else if line.type === 'success'}
              <span class="term-prefix">&#10003;</span>
              <span class="term-text">{line.text}</span>
            {:else if line.type === 'info'}
              <span class="term-prefix">i</span>
              <span class="term-text">{line.text}</span>
            {:else}
              <span class="term-prefix">&nbsp;</span>
              <span class="term-text">{line.text}</span>
            {/if}
          </div>
        {/each}
      {/if}
    </div>
  {/if}
</div>

<style>
  .terminal-panel {
    position: relative;
    flex-shrink: 0;
    border-top: 1px solid var(--border-color);
    background: var(--bg-secondary);
    z-index: 50;
  }

  .terminal-panel.open {
    height: 240px;
    display: flex;
    flex-direction: column;
  }

  .terminal-tab {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    padding: 6px 16px;
    font-size: 12px;
    font-weight: 600;
    color: var(--text-secondary);
    background: var(--bg-secondary);
    border: none;
    cursor: pointer;
    text-align: left;
    transition: background 0.1s ease;
  }

  .terminal-tab:hover {
    background: var(--bg-hover);
  }

  .tab-label {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .tab-icon {
    font-size: 8px;
    opacity: 0.6;
  }

  .badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 18px;
    height: 18px;
    padding: 0 5px;
    border-radius: 9px;
    background: var(--accent);
    color: #fff;
    font-size: 10px;
    font-weight: 700;
  }

  .spinner {
    width: 12px;
    height: 12px;
    border: 2px solid var(--border-color);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .chevron {
    margin-left: auto;
    font-size: 10px;
    transition: transform 0.15s ease;
    transform: rotate(180deg);
  }

  .chevron.open {
    transform: rotate(0deg);
  }

  .terminal-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 4px 16px;
    border-bottom: 1px solid var(--border-color);
    font-size: 11px;
    flex-shrink: 0;
  }

  .toolbar-left {
    color: var(--text-muted);
  }

  .toolbar-right {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .auto-scroll-toggle {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 11px;
    color: var(--text-muted);
    cursor: pointer;
  }

  .auto-scroll-toggle input {
    margin: 0;
  }

  .toolbar-btn {
    padding: 2px 10px;
    font-size: 11px;
    font-weight: 500;
    color: var(--text-secondary);
    background: var(--bg-hover);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    cursor: pointer;
    transition: all 0.1s ease;
  }

  .toolbar-btn:hover {
    background: var(--border-color);
    color: var(--text-primary);
  }

  .terminal-body {
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
    padding: 8px 0;
    font-family: var(--font-mono);
    font-size: 12px;
    line-height: 1.6;
    background: var(--bg-primary);
  }

  .empty-state {
    padding: 24px 16px;
    text-align: center;
    color: var(--text-muted);
    font-family: var(--font-sans, system-ui);
    font-size: 12px;
  }

  .term-line {
    display: flex;
    padding: 0 16px;
    white-space: pre-wrap;
    word-break: break-all;
  }

  .term-line:hover {
    background: var(--bg-hover);
  }

  .term-time {
    flex-shrink: 0;
    width: 64px;
    color: var(--text-muted);
    opacity: 0.6;
    user-select: none;
  }

  .term-prefix {
    flex-shrink: 0;
    width: 16px;
    text-align: center;
    user-select: none;
  }

  .term-text {
    flex: 1;
    min-width: 0;
  }

  /* Line type colors */
  .term-line.command {
    color: var(--accent);
    font-weight: 600;
  }

  .term-line.command .term-prefix {
    color: var(--accent);
  }

  .term-line.stdout {
    color: var(--text-primary);
  }

  .term-line.stderr {
    color: var(--warning);
  }

  .term-line.stderr .term-prefix {
    color: var(--warning);
  }

  .term-line.error {
    color: var(--error);
  }

  .term-line.error .term-prefix {
    color: var(--error);
  }

  .term-line.success {
    color: var(--success);
  }

  .term-line.success .term-prefix {
    color: var(--success);
  }

  .term-line.info {
    color: var(--text-secondary);
    font-style: italic;
  }

  .term-line.info .term-prefix {
    color: var(--accent);
  }

  .line-count {
    font-variant-numeric: tabular-nums;
  }
</style>
