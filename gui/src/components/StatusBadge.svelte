<script lang="ts">
  interface Props {
    status: 'unknown' | 'ready' | 'syncing' | 'error' | 'success' | 'failed' | 'cancelled';
    size?: 'sm' | 'md';
  }

  let { status, size = 'sm' }: Props = $props();

  const colorMap: Record<string, string> = {
    unknown: 'var(--text-muted)',
    ready: 'var(--success)',
    syncing: 'var(--warning)',
    error: 'var(--error)',
    success: 'var(--success)',
    failed: 'var(--error)',
    cancelled: 'var(--text-muted)'
  };
</script>

<span
  class="status-badge"
  class:sm={size === 'sm'}
  class:md={size === 'md'}
  style="--dot-color: {colorMap[status] || 'var(--text-muted)'}"
  title={status}
>
  <span class="dot"></span>
</span>

<style>
  .status-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .dot {
    display: block;
    border-radius: 50%;
    background-color: var(--dot-color);
  }

  .sm .dot {
    width: 8px;
    height: 8px;
  }

  .md .dot {
    width: 10px;
    height: 10px;
  }
</style>
