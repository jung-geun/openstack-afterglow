<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props {
    breadcrumb: string;
    title: string;
    subtitle?: string;
    actions?: Snippet;
    class?: string;
  }

  let { breadcrumb, title, subtitle, actions, class: className = '' }: Props = $props();
</script>

<div class="page-header {className}">
  <div>
    <div class="page-header-breadcrumb">
      <span class="md:hidden">{breadcrumb.includes(' / ') ? breadcrumb.split(' / ').at(-1) : breadcrumb}</span>
      <span class="hidden md:inline">{breadcrumb}</span>
    </div>
    <h1 class="page-header-title">{title}</h1>
    {#if subtitle}
      <p class="page-header-subtitle">{subtitle}</p>
    {/if}
  </div>
  {#if actions}
    <div class="page-header-actions">
      {@render actions()}
    </div>
  {/if}
</div>

<style>
  .page-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
    margin-bottom: 1.5rem;
  }
  .page-header-breadcrumb {
    margin-bottom: 0.25rem;
    font-size: 0.6875rem;
    text-transform: uppercase;
    letter-spacing: 0.16em;
    font-weight: 500;
    color: var(--color-ink-3);
  }
  .page-header-title {
    margin: 0;
    font-size: 1.375rem;
    font-weight: 700;
    line-height: 1.15;
    color: var(--color-ink-0);
  }
  .page-header-subtitle {
    margin: 0.125rem 0 0;
    font-size: 0.8125rem;
    color: var(--color-ink-2);
  }
  .page-header-actions {
    display: flex;
    align-items: center;
    gap: 0.625rem;
    flex-shrink: 0;
    margin-left: 1rem;
    margin-top: 0.125rem;
  }
</style>
