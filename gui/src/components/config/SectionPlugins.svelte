<script lang="ts">
  import type { SiteConfig } from '$lib/types';
  import TagInput from '../TagInput.svelte';

  interface Props {
    config: SiteConfig;
    onchange: (config: SiteConfig) => void;
  }

  let { config, onchange }: Props = $props();

  function updatePlugins(
    env: 'live' | 'local',
    action: 'activate' | 'deactivate',
    tags: string[]
  ) {
    onchange({
      ...config,
      plugins: {
        ...config.plugins,
        [env]: { ...config.plugins[env], [action]: tags }
      }
    });
  }
</script>

<div class="plugins-grid">
  <div class="plugin-column">
    <h4 class="column-label">Live Environment</h4>

    <div class="field">
      <label>Plugins to Activate</label>
      <TagInput
        tags={config.plugins.live.activate}
        placeholder="Add plugin slug..."
        onchange={(tags) => updatePlugins('live', 'activate', tags)}
      />
    </div>

    <div class="field">
      <label>Plugins to Deactivate</label>
      <TagInput
        tags={config.plugins.live.deactivate}
        placeholder="Add plugin slug..."
        onchange={(tags) => updatePlugins('live', 'deactivate', tags)}
      />
    </div>
  </div>

  <div class="plugin-column">
    <h4 class="column-label">Local Environment</h4>

    <div class="field">
      <label>Plugins to Activate</label>
      <TagInput
        tags={config.plugins.local.activate}
        placeholder="Add plugin slug..."
        onchange={(tags) => updatePlugins('local', 'activate', tags)}
      />
    </div>

    <div class="field">
      <label>Plugins to Deactivate</label>
      <TagInput
        tags={config.plugins.local.deactivate}
        placeholder="Add plugin slug..."
        onchange={(tags) => updatePlugins('local', 'deactivate', tags)}
      />
    </div>
  </div>
</div>

<style>
  .plugins-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
    padding-top: 12px;
  }

  .plugin-column {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .column-label {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding-bottom: 4px;
    border-bottom: 1px solid var(--border-color);
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
</style>
