<script lang="ts">
  interface Props {
    tags: string[];
    placeholder?: string;
    onchange?: (tags: string[]) => void;
  }

  let { tags = [], placeholder = 'Add item...', onchange }: Props = $props();

  let inputValue = $state('');

  function addTag() {
    const value = inputValue.trim();
    if (value && !tags.includes(value)) {
      const newTags = [...tags, value];
      inputValue = '';
      onchange?.(newTags);
    }
  }

  function removeTag(index: number) {
    const newTags = tags.filter((_, i) => i !== index);
    onchange?.(newTags);
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Enter') {
      event.preventDefault();
      addTag();
    } else if (event.key === 'Backspace' && inputValue === '' && tags.length > 0) {
      removeTag(tags.length - 1);
    }
  }
</script>

<div class="tag-input-container">
  <div class="tags-area">
    {#each tags as tag, i (tag)}
      <span class="tag">
        <span class="tag-text">{tag}</span>
        <button class="tag-remove" onclick={() => removeTag(i)} title="Remove">&times;</button>
      </span>
    {/each}
    <input
      type="text"
      class="tag-input"
      bind:value={inputValue}
      {placeholder}
      onkeydown={handleKeydown}
    />
  </div>
</div>

<style>
  .tag-input-container {
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    background: var(--bg-input);
    padding: 4px 8px;
    min-height: 38px;
    cursor: text;
    transition: border-color 0.15s ease;
  }

  .tag-input-container:focus-within {
    border-color: var(--accent);
    box-shadow: 0 0 0 3px var(--accent-subtle);
  }

  .tags-area {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    align-items: center;
  }

  .tag {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 8px;
    background: var(--accent-subtle);
    color: var(--accent);
    border-radius: var(--radius-sm);
    font-size: 12px;
    font-weight: 500;
  }

  .tag-text {
    max-width: 200px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .tag-remove {
    font-size: 14px;
    line-height: 1;
    color: var(--accent);
    opacity: 0.6;
    padding: 0 2px;
  }

  .tag-remove:hover {
    opacity: 1;
  }

  .tag-input {
    flex: 1;
    min-width: 100px;
    border: none;
    background: transparent;
    padding: 4px 0;
    font-size: 13px;
    outline: none;
    box-shadow: none;
  }
</style>
