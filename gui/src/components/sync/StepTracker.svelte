<script lang="ts">
  import type { SyncStep } from '$lib/types';

  interface Props {
    steps: SyncStep[];
  }

  let { steps }: Props = $props();

  function statusIcon(status: SyncStep['status']): string {
    switch (status) {
      case 'pending':
        return '\u25CB'; // ○
      case 'in_progress':
        return '\u25B6'; // ►
      case 'completed':
        return '\u2713'; // ✓
      case 'failed':
        return '\u2717'; // ✗
      default:
        return '\u25CB';
    }
  }

  function statusClass(status: SyncStep['status']): string {
    switch (status) {
      case 'pending':
        return 'step-pending';
      case 'in_progress':
        return 'step-active';
      case 'completed':
        return 'step-completed';
      case 'failed':
        return 'step-failed';
      default:
        return 'step-pending';
    }
  }
</script>

<div class="step-tracker">
  {#each steps as step, i (step.name)}
    <div class="step {statusClass(step.status)}">
      <div class="step-indicator">
        <span class="step-icon">{statusIcon(step.status)}</span>
        {#if i < steps.length - 1}
          <div class="step-line"></div>
        {/if}
      </div>
      <div class="step-content">
        <span class="step-name">{step.name}</span>
        {#if step.output}
          <span class="step-output">{step.output}</span>
        {/if}
      </div>
    </div>
  {/each}
</div>

<style>
  .step-tracker {
    display: flex;
    flex-direction: column;
    gap: 0;
  }

  .step {
    display: flex;
    gap: 12px;
    min-height: 40px;
  }

  .step-indicator {
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 24px;
    flex-shrink: 0;
  }

  .step-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    border-radius: 50%;
    font-size: 13px;
    flex-shrink: 0;
  }

  .step-line {
    width: 2px;
    flex: 1;
    min-height: 16px;
    background: var(--border-color);
  }

  .step-content {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding-bottom: 12px;
  }

  .step-name {
    font-size: 13px;
    font-weight: 500;
    line-height: 24px;
  }

  .step-output {
    font-size: 12px;
    color: var(--text-muted);
    font-family: var(--font-mono);
  }

  /* Status colors */
  .step-pending .step-icon {
    color: var(--text-muted);
    background: var(--bg-input);
  }

  .step-pending .step-name {
    color: var(--text-muted);
  }

  .step-active .step-icon {
    color: var(--accent);
    background: var(--accent-subtle);
    animation: pulse 1.5s ease-in-out infinite;
  }

  .step-active .step-name {
    color: var(--accent);
  }

  .step-completed .step-icon {
    color: var(--success);
    background: rgba(34, 197, 94, 0.15);
  }

  .step-completed .step-name {
    color: var(--text-secondary);
  }

  .step-failed .step-icon {
    color: var(--error);
    background: rgba(239, 68, 68, 0.15);
  }

  .step-failed .step-name {
    color: var(--error);
  }

  @keyframes pulse {
    0%,
    100% {
      opacity: 1;
    }
    50% {
      opacity: 0.5;
    }
  }
</style>
