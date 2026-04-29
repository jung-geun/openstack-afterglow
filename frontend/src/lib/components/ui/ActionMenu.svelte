<script lang="ts">
  import { tick } from 'svelte';
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
  let pos = $state({ menuTop: 0, menuBottom: 0, left: 0, openUp: false });

  async function computePosition() {
    if (!triggerEl) return;
    await tick();
    const rect = triggerEl.getBoundingClientRect();
    const spaceBelow = window.innerHeight - rect.bottom;
    pos = {
      menuTop: rect.bottom + 4,
      menuBottom: window.innerHeight - rect.top + 4,
      left: rect.right,
      openUp: spaceBelow < 160,
    };
  }

  $effect(() => {
    if (open) computePosition();
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
  onclick={(e) => { e.stopPropagation(); open ? onclose() : onopen(); }}
  class="w-7 h-7 flex items-center justify-center rounded-md text-gray-400
         hover:text-white hover:bg-gray-700/50 transition-colors {buttonClass}"
>
  <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
    <path d="M10 6a2 2 0 110-4 2 2 0 010 4zM10 12a2 2 0 110-4 2 2 0 010 4zM10 18a2 2 0 110-4 2 2 0 010 4z"/>
  </svg>
</button>

{#if open}
  <div
    class="fixed z-[9999] min-w-[140px] bg-gray-900 border border-gray-700 rounded-lg shadow-xl py-1"
    style:left="{pos.left}px"
    style:top={pos.openUp ? 'auto' : `${pos.menuTop}px`}
    style:bottom={pos.openUp ? `${pos.menuBottom}px` : 'auto'}
    style:transform="translateX(-100%)"
    onclick={(e) => e.stopPropagation()}
    role="menu"
  >
    {@render children()}
  </div>
{/if}
