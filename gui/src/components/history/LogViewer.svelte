<script lang="ts">
  import type { SyncHistoryEntry } from '$lib/types';
  import LogOutput from '../sync/LogOutput.svelte';

  interface Props {
    entry: SyncHistoryEntry;
    onclose: () => void;
  }

  let { entry, onclose }: Props = $props();

  let logLines = $derived(entry.log ? entry.log.split('\n') : ['No log output recorded.']);

  function formatDuration(seconds: number): string {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    if (mins > 0) return `${mins}m ${secs}s`;
    return `${secs}s`;
  }

  function formatDate(dateStr: string): string {
    try {
      return new Date(dateStr).toLocaleString();
    } catch {
      return dateStr;
    }
  }

  async function copyLog() {
    try {
      await navigator.clipboard.writeText(entry.log || '');
    } catch {
      // Ignore
    }
  }

  function handleOverlayClick(e: MouseEvent) {
    if (e.target === e.currentTarget) onclose();
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') onclose();
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="modal-overlay" onclick={handleOverlayClick}>
  <div class="modal-content" role="dialog" aria-modal="true" aria-label="Sync Log Viewer">
    <div class="modal-header">
      <div class="modal-title-row">
        <h3>Sync Log</h3>
        <button class="close-btn" onclick={onclose} aria-label="Close">&times;</button>
      </div>

      <div class="meta-row">
        <span class="meta-item">
          <span class="meta-label">Site:</span>
          <span class="meta-value">{entry.site_name}</span>
        </span>
        <span class="meta-item">
          <span class="meta-label">Direction:</span>
          <span class="meta-value direction" class:push={entry.direction === 'push'} class:pull={entry.direction === 'pull'}>
            {entry.direction === 'push' ? '\u2191 Push' : '\u2193 Pull'}
          </span>
        </span>
        <span class="meta-item">
          <span class="meta-label">Date:</span>
          <span class="meta-value">{formatDate(entry.started_at)}</span>
        </span>
        <span class="meta-item">
          <span class="meta-label">Duration:</span>
          <span class="meta-value">{formatDuration(entry.duration_seconds)}</span>
        </span>
        <span class="meta-item">
          <span class="meta-label">Status:</span>
          <span class="meta-value status" class:success={entry.status === 'success'} class:failed={entry.status === 'failed'} class:cancelled={entry.status === 'cancelled'}>
            {entry.status === 'success' ? '\u2713 Success' : entry.status === 'failed' ? '\u2717 Failed' : '\u2298 Cancelled'}
          </span>
        </span>
      </div>
    </div>

    <div class="modal-body">
      <LogOutput lines={logLines} />
    </div>

    <div class="modal-footer">
      <button class="btn btn-secondary" onclick={copyLog}>Copy Log</button>
      <button class="btn btn-primary" onclick={onclose}>Close</button>
    </div>
  </div>
</div>

<style>
  .modal-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
    padding: 24px;
  }

  .modal-content {
    background: var(--bg-primary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    width: 100%;
    max-width: 900px;
    max-height: 85vh;
    display: flex;
    flex-direction: column;
    box-shadow: var(--shadow-lg);
  }

  .modal-header {
    padding: 20px 24px 16px;
    border-bottom: 1px solid var(--border-color);
    flex-shrink: 0;
  }

  .modal-title-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
  }

  .modal-title-row h3 {
    font-size: 18px;
    font-weight: 600;
  }

  .close-btn {
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    color: var(--text-muted);
    border-radius: var(--radius-sm);
    transition: all 0.15s ease;
  }

  .close-btn:hover {
    background: var(--bg-hover);
    color: var(--text-primary);
  }

  .meta-row {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
  }

  .meta-item {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 12px;
  }

  .meta-label {
    color: var(--text-muted);
    font-weight: 500;
  }

  .meta-value {
    font-weight: 600;
    color: var(--text-secondary);
  }

  .direction.push { color: var(--error); }
  .direction.pull { color: var(--success); }
  .status.success { color: var(--success); }
  .status.failed { color: var(--error); }
  .status.cancelled { color: var(--text-muted); }

  .modal-body {
    flex: 1;
    overflow: hidden;
    padding: 16px 24px;
  }

  .modal-footer {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    padding: 12px 24px;
    border-top: 1px solid var(--border-color);
    flex-shrink: 0;
  }

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

  .btn-primary:hover {
    background: var(--accent-hover);
  }

  .btn-secondary {
    background: var(--bg-hover);
    color: var(--text-secondary);
  }

  .btn-secondary:hover {
    background: var(--border-color);
    color: var(--text-primary);
  }
</style>
