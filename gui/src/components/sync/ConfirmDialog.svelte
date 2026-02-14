<script lang="ts">
  interface Props {
    message: string;
    confirmLabel?: string;
    cancelLabel?: string;
    onconfirm: () => void;
    oncancel: () => void;
  }

  let {
    message,
    confirmLabel = 'Confirm',
    cancelLabel = 'Cancel',
    onconfirm,
    oncancel,
  }: Props = $props();

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      oncancel();
    } else if (e.key === 'Enter') {
      onconfirm();
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="dialog-backdrop" role="presentation" onclick={oncancel}>
  <!-- svelte-ignore a11y_click_events_have_key_events -->
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <!-- svelte-ignore a11y_interactive_supports_focus -->
  <div class="dialog" onclick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
    <div class="dialog-body">
      <p class="dialog-message">{message}</p>
    </div>
    <div class="dialog-actions">
      <button class="btn btn-secondary" onclick={oncancel}>
        {cancelLabel}
      </button>
      <button class="btn btn-primary" onclick={onconfirm}>
        {confirmLabel}
      </button>
    </div>
  </div>
</div>

<style>
  .dialog-backdrop {
    position: fixed;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(0, 0, 0, 0.6);
    z-index: 1000;
  }

  .dialog {
    background: var(--bg-card);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-lg);
    min-width: 360px;
    max-width: 500px;
    overflow: hidden;
  }

  .dialog-body {
    padding: 24px;
  }

  .dialog-message {
    font-size: 14px;
    line-height: 1.6;
    color: var(--text-primary);
  }

  .dialog-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    padding: 12px 24px;
    background: var(--bg-secondary);
    border-top: 1px solid var(--border-color);
  }

  .btn {
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 500;
    border-radius: var(--radius-sm);
    transition: all 0.15s ease;
  }

  .btn-secondary {
    background: var(--bg-hover);
    color: var(--text-secondary);
  }

  .btn-secondary:hover {
    background: var(--border-color);
    color: var(--text-primary);
  }

  .btn-primary {
    background: var(--accent);
    color: #fff;
  }

  .btn-primary:hover {
    background: var(--accent-hover);
  }
</style>
