<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props {
    open: boolean;
    onopen: () => void;
    onclose: () => void;
    children: Snippet;
    buttonClass?: string;
  }

  let { open, onopen, onclose, children, buttonClass = '' }: Props = $props();

  let triggerEl = $state<HTMLButtonElement | null>(null);
  let pos = $state<null | { top: number; bottom: number; left: number; openUp: boolean }>(null);

  function computePosition() {
    if (!triggerEl) return;
    const rect = triggerEl.getBoundingClientRect();
    const spaceBelow = window.innerHeight - rect.bottom;
    pos = {
      top: rect.bottom + 4,
      bottom: window.innerHeight - rect.top + 4,
      left: rect.right,
      openUp: spaceBelow < 160,
    };
  }

  function handleTriggerClick(e: MouseEvent) {
    e.stopPropagation();
    if (open) {
      onclose();
    } else {
      computePosition();
      onopen();
    }
  }

  $effect(() => {
    if (open && pos === null) computePosition();
    if (!open) pos = null;
  });

  $effect(() => {
    if (!open) return;
    const reposition = () => computePosition();
    window.addEventListener('scroll', reposition, true);
    window.addEventListener('resize', reposition);
    return () => {
      window.removeEventListener('scroll', reposition, true);
      window.removeEventListener('resize', reposition);
    };
  });

  $effect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (triggerEl?.contains(e.target as Node)) return;
      onclose();
    }
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onclose();
    }
    document.addEventListener('click', handleClick, true);
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('click', handleClick, true);
      document.removeEventListener('keydown', handleKey);
    };
  });
</script>

<button
  bind:this={triggerEl}
  type="button"
  onclick={handleTriggerClick}
  class="action-trigger {buttonClass}"
>
  <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
    <path d="M10 6a2 2 0 110-4 2 2 0 010 4zM10 12a2 2 0 110-4 2 2 0 010 4zM10 18a2 2 0 110-4 2 2 0 010 4z"/>
  </svg>
</button>

{#if open && pos}
  <div
    class="action-menu"
    style:left="{pos.left}px"
    style:top={pos.openUp ? 'auto' : `${pos.top}px`}
    style:bottom={pos.openUp ? `${pos.bottom}px` : 'auto'}
    style:transform="translateX(-100%)"
  >
    {@render children()}
  </div>
{/if}

<style>
  .action-trigger {
    width: 1.75rem;
    height: 1.75rem;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 0.375rem;
    color: var(--color-ink-2);
    background: transparent;
    transition: background var(--motion-duration-fast) var(--motion-ease-standard), color var(--motion-duration-fast) var(--motion-ease-standard);
  }
  .action-trigger:hover {
    color: var(--color-ink-0);
    background: color-mix(in oklab, var(--color-surface-sunken) 65%, transparent);
  }
  .action-menu {
    position: fixed;
    z-index: var(--z-popover);
    min-width: 8.75rem;
    padding-block: 0.25rem;
    border: 1px solid var(--color-line-2);
    border-radius: 0.5rem;
    background: var(--color-surface-raised);
    box-shadow: 0 10px 25px color-mix(in oklab, var(--color-surface-canvas) 60%, transparent);
  }
</style>
