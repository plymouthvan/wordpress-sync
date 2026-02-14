<script lang="ts">
  interface Props {
    lines: string[];
  }

  let { lines }: Props = $props();

  let scrollContainer: HTMLDivElement | undefined = $state(undefined);
  let autoScroll = $state(true);
  let userScrolledUp = $state(false);

  // Cap rendered lines to avoid DOM bloat. Show the last N lines only.
  const MAX_RENDERED_LINES = 2000;
  let visibleLines = $derived(
    lines.length > MAX_RENDERED_LINES
      ? lines.slice(lines.length - MAX_RENDERED_LINES)
      : lines
  );
  let truncatedCount = $derived(
    lines.length > MAX_RENDERED_LINES
      ? lines.length - MAX_RENDERED_LINES
      : 0
  );

  // Track if user manually scrolled up
  function handleScroll() {
    if (!scrollContainer) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollContainer;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 30;

    if (isAtBottom) {
      userScrolledUp = false;
      autoScroll = true;
    } else {
      userScrolledUp = true;
      autoScroll = false;
    }
  }

  // Auto-scroll to bottom when new lines arrive (throttled)
  let lastScrolledLength = 0;
  $effect(() => {
    const len = lines.length;
    // Only scroll if lines actually grew since last scroll
    if (autoScroll && scrollContainer && len > lastScrolledLength) {
      lastScrolledLength = len;
      requestAnimationFrame(() => {
        if (scrollContainer) {
          scrollContainer.scrollTop = scrollContainer.scrollHeight;
        }
      });
    }
  });

  function enableAutoScroll() {
    autoScroll = true;
    userScrolledUp = false;
    if (scrollContainer) {
      scrollContainer.scrollTop = scrollContainer.scrollHeight;
    }
  }

  async function copyLog() {
    const text = lines.join('\n');
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // Fallback: ignore
    }
  }
</script>

<div class="log-output-wrapper">
  <div class="log-toolbar">
    <span class="log-label">Output <span class="line-count">({lines.length} lines)</span></span>
    <div class="log-actions">
      {#if userScrolledUp}
        <button class="log-btn scroll-btn" onclick={enableAutoScroll}>
          Auto-scroll
        </button>
      {/if}
      <button class="log-btn" onclick={copyLog} title="Copy log to clipboard">
        Copy
      </button>
    </div>
  </div>
  <div
    class="log-container"
    bind:this={scrollContainer}
    onscroll={handleScroll}
    role="log"
    aria-live="off"
  >
    {#if truncatedCount > 0}
      <div class="log-truncated">... {truncatedCount} earlier lines hidden ...</div>
    {/if}
    {#each visibleLines as line, i}
      <div class="log-line">{line}</div>
    {/each}
    {#if lines.length === 0}
      <div class="log-empty">Waiting for output...</div>
    {/if}
  </div>
</div>

<style>
  .log-output-wrapper {
    display: flex;
    flex-direction: column;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    overflow: hidden;
  }

  .log-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 12px;
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border-color);
  }

  .log-label {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .line-count {
    font-weight: 400;
    font-variant-numeric: tabular-nums;
    text-transform: none;
    letter-spacing: 0;
  }

  .log-actions {
    display: flex;
    gap: 6px;
  }

  .log-btn {
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 500;
    border-radius: var(--radius-sm);
    background: var(--bg-hover);
    color: var(--text-secondary);
    transition: all 0.15s ease;
  }

  .log-btn:hover {
    background: var(--border-color);
    color: var(--text-primary);
  }

  .scroll-btn {
    background: var(--accent-subtle);
    color: var(--accent);
  }

  .log-container {
    background: #0d1117;
    color: #c9d1d9;
    font-family: var(--font-mono);
    font-size: 12px;
    line-height: 1.6;
    padding: 12px;
    max-height: 360px;
    min-height: 160px;
    overflow-y: auto;
    overflow-x: auto;
    white-space: pre;
  }

  .log-line {
    padding: 0 4px;
  }

  .log-line:hover {
    background: rgba(255, 255, 255, 0.04);
  }

  .log-empty {
    color: #484f58;
    font-style: italic;
  }

  .log-truncated {
    color: #484f58;
    font-style: italic;
    padding: 0 4px 4px;
  }
</style>
