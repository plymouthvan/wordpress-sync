<script lang="ts">
  import type { SiteConfig } from '$lib/types';

  interface Props {
    config: SiteConfig;
    onchange: (config: SiteConfig) => void;
  }

  let { config, onchange }: Props = $props();

  function update(key: keyof SiteConfig['ownership'], value: string) {
    onchange({ ...config, ownership: { ...config.ownership, [key]: value } });
  }
</script>

<div class="form-grid">
  <div class="field">
    <label for="owner-user">File Owner User</label>
    <input
      id="owner-user"
      type="text"
      value={config.ownership.user}
      oninput={(e) => update('user', e.currentTarget.value)}
      placeholder="www-data"
    />
  </div>

  <div class="field">
    <label for="owner-group">File Owner Group</label>
    <input
      id="owner-group"
      type="text"
      value={config.ownership.group}
      oninput={(e) => update('group', e.currentTarget.value)}
      placeholder="www-data"
    />
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

  .field input {
    width: 100%;
  }
</style>
