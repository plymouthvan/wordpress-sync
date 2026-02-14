<script lang="ts">
  import type { SiteConfig } from '$lib/types';

  interface Props {
    config: SiteConfig;
    onchange: (config: SiteConfig) => void;
  }

  let { config, onchange }: Props = $props();

  function updateDirection(value: string) {
    onchange({
      ...config,
      operation: { ...config.operation, direction: value as 'push' | 'pull' }
    });
  }
</script>

<div class="form-grid">
  <div class="field">
    <label for="op-direction">Default Direction</label>
    <select
      id="op-direction"
      value={config.operation.direction}
      onchange={(e) => updateDirection(e.currentTarget.value)}
    >
      <option value="push">Push (Local → Live)</option>
      <option value="pull">Pull (Live → Local)</option>
    </select>
  </div>
</div>

<style>
  .form-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    padding-top: 12px;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .field label {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }

  .field select {
    width: 100%;
  }
</style>
