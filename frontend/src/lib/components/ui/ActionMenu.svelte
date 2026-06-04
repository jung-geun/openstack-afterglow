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

  // 외부에서 open=true 가 주입된 경우 fallback. close 시 pos clear.
  $effect(() => {
    if (open && pos === null) computePosition();
    if (!open) pos = null;
  });

  // open 동안 scroll(capture) / resize 추적
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

  // 외부 클릭 / Escape 로 닫기
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
  onclick={handleTriggerClick}
  class="w-7 h-7 flex items-center justify-center rounded-md text-gray-400
         hover:text-white hover:bg-gray-700/50 transition-colors {buttonClass}"
>
  <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
    <path d="M10 6a2 2 0 110-4 2 2 0 010 4zM10 12a2 2 0 110-4 2 2 0 010 4zM10 18a2 2 0 110-4 2 2 0 010 4z"/>
  </svg>
</button>

{#if open && pos}
  <div
    class="fixed z-[9999] min-w-[140px] bg-gray-900 border border-gray-700 rounded-lg shadow-xl py-1"
    style:left="{pos.left}px"
    style:top={pos.openUp ? 'auto' : `${pos.top}px`}
    style:bottom={pos.openUp ? `${pos.bottom}px` : 'auto'}
    style:transform="translateX(-100%)"
    onclick={(e) => e.stopPropagation()}
    role="menu"
  >
    {@render children()}
  </div>
{/if}
