<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props {
    title: string;
    open?: boolean;
    children: Snippet;
  }

  let { title, open = $bindable(false), children }: Props = $props();

  function toggle() {
    open = !open;
  }
</script>

<section class="collapsible-section">
  <button class="section-header" onclick={toggle} type="button">
    <span class="chevron" class:open>{@html '&#9654;'}</span>
    <h3 class="section-title">{title}</h3>
  </button>
  {#if open}
    <div class="section-body">
      {@render children()}
    </div>
  {/if}
</section>

<style>
  .collapsible-section {
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    background: var(--bg-card);
    overflow: hidden;
  }

  .section-header {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    padding: 14px 20px;
    text-align: left;
    cursor: pointer;
    background: transparent;
    transition: background 0.15s ease;
  }

  .section-header:hover {
    background: var(--bg-hover);
  }

  .chevron {
    font-size: 10px;
    color: var(--text-muted);
    transition: transform 0.2s ease;
    display: inline-block;
    flex-shrink: 0;
  }

  .chevron.open {
    transform: rotate(90deg);
  }

  .section-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary);
  }

  .section-body {
    padding: 4px 20px 20px;
    border-top: 1px solid var(--border-color);
  }
</style>
