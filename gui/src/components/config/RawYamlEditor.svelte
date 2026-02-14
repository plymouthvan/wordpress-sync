<script lang="ts">
  import YAML from 'yaml';
  import { revealItemInDir } from '@tauri-apps/plugin-opener';
  import { getSiteConfigPath } from '$lib/services/config';
  import type { SiteConfig } from '$lib/types';

  interface Props {
    config: SiteConfig;
    onchange: (config: SiteConfig) => void;
  }

  let { config, onchange }: Props = $props();

  let yamlError = $state('');

  // Generate YAML from config (stripping the name field)
  let yamlText = $derived.by(() => {
    const { name: _name, ...yamlData } = config;
    try {
      return YAML.stringify(yamlData, { indent: 2 });
    } catch {
      return '';
    }
  });

  let editedYaml = $state('');
  let isEditing = $state(false);

  // Sync from derived yamlText when not actively editing
  $effect(() => {
    if (!isEditing) {
      editedYaml = yamlText;
    }
  });

  function handleInput(e: Event) {
    const target = e.target as HTMLTextAreaElement;
    editedYaml = target.value;
    isEditing = true;
    yamlError = '';

    try {
      const parsed = YAML.parse(editedYaml);
      if (parsed && typeof parsed === 'object') {
        onchange({ name: config.name, ...parsed } as SiteConfig);
        yamlError = '';
      }
    } catch (err) {
      yamlError = err instanceof Error ? err.message : 'Invalid YAML';
    }
  }

  function handleBlur() {
    // When user stops editing, allow sync from form again
    if (!yamlError) {
      isEditing = false;
    }
  }

  async function revealInFinder() {
    try {
      const filePath = await getSiteConfigPath(config.name);
      await revealItemInDir(filePath);
    } catch (err) {
      console.error('Failed to reveal config file:', err);
    }
  }
</script>

<div class="yaml-editor">
  <div class="yaml-toolbar">
    <span class="toolbar-label">~/.wordpress-sync/sites/{config.name}.yaml</span>
    <button class="btn-reveal" onclick={revealInFinder} title="Show in Finder">
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
        <path d="M2 4h12M2 4v8a2 2 0 002 2h8a2 2 0 002-2V4M2 4l1.5-2h9L14 4" />
      </svg>
      Show in Finder
    </button>
  </div>
  {#if yamlError}
    <div class="yaml-error">
      <span class="error-icon">!</span>
      <span class="error-text">{yamlError}</span>
    </div>
  {/if}
  <textarea
    class="yaml-textarea"
    value={isEditing ? editedYaml : yamlText}
    oninput={handleInput}
    onblur={handleBlur}
    onfocus={() => { isEditing = true; editedYaml = yamlText; }}
    spellcheck="false"
    autocomplete="off"
    data-autocorrect="off"
    data-autocapitalize="off"
  ></textarea>
</div>

<style>
  .yaml-editor {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 500px;
  }

  .yaml-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 8px 12px;
    margin-bottom: 8px;
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
  }

  .toolbar-label {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--text-secondary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .btn-reveal {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    font-size: 12px;
    font-weight: 500;
    color: var(--text-secondary);
    background: var(--bg-primary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    cursor: pointer;
    white-space: nowrap;
    transition: all 0.15s ease;
  }

  .btn-reveal:hover {
    color: var(--text-primary);
    border-color: var(--accent);
    background: var(--accent-subtle);
  }

  .yaml-error {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px 16px;
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid var(--error);
    border-radius: var(--radius-sm);
    margin-bottom: 12px;
    color: var(--error);
    font-size: 13px;
  }

  .error-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
    background: var(--error);
    color: #fff;
    border-radius: 50%;
    font-size: 12px;
    font-weight: 700;
    flex-shrink: 0;
  }

  .error-text {
    flex: 1;
    word-break: break-word;
  }

  .yaml-textarea {
    flex: 1;
    width: 100%;
    min-height: 500px;
    font-family: var(--font-mono);
    font-size: 13px;
    line-height: 1.6;
    padding: 16px;
    background: var(--bg-input);
    color: var(--text-primary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    resize: vertical;
    tab-size: 2;
    white-space: pre;
    overflow-wrap: normal;
    overflow-x: auto;
  }

  .yaml-textarea:focus {
    border-color: var(--accent);
    box-shadow: 0 0 0 3px var(--accent-subtle);
  }
</style>
