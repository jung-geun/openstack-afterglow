<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props {
    icon?: string;
    headline: string;
    description?: string;
    cta?: Snippet;
    class?: string;
  }

  let { icon, headline, description, cta, class: className = '' }: Props = $props();
</script>

<div class="empty-state flex flex-col items-center justify-center py-16 px-4 text-center {className}">
  {#if icon}
    <div class="empty-icon-wrap mb-4">
      <svg class="w-10 h-10 empty-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d={icon}/>
      </svg>
    </div>
  {/if}
  <div class="text-[15px] font-semibold text-ink-0 mb-1">{headline}</div>
  {#if description}
    <div class="text-[13px] text-ink-2 max-w-xs">{description}</div>
  {/if}
  {#if cta}
    <div class="mt-4">{@render cta()}</div>
  {/if}
</div>

<style>
  .empty-icon-wrap {
    position: relative;
    width: 64px;
    height: 64px;
    border-radius: 16px;
    background: var(--warm-soft);
    border: 1px solid var(--warm-ring);
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .empty-icon-wrap::before {
    content: "";
    position: absolute;
    inset: -12px;
    border-radius: 24px;
    background: radial-gradient(circle at center, var(--color-warm) 0%, transparent 70%);
    opacity: 0.08;
    pointer-events: none;
  }
  .empty-icon {
    color: var(--color-warm);
  }
</style>
