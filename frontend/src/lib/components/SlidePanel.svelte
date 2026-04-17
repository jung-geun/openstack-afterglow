<script lang="ts">
  import { fly, fade } from 'svelte/transition';
  import type { Snippet } from 'svelte';

  interface Props {
    onClose: () => void;
    width?: string;
    children: Snippet;
  }

  let { onClose, width = 'w-full md:w-[75vw] max-w-5xl', children }: Props = $props();
</script>

<div class="fixed inset-0 z-40" role="dialog" aria-modal="true"
     onkeydown={(e) => e.key === 'Escape' && onClose()} tabindex="-1">
  <button
    class="absolute inset-0 bg-black/50 cursor-default"
    transition:fade={{ duration: 200 }}
    onclick={onClose}
    aria-label="패널 닫기"
  ></button>
  <div
    class="absolute right-0 top-14 bottom-0 {width} bg-gray-950 border-l border-gray-700 overflow-y-auto shadow-2xl"
    transition:fly={{ x: 400, duration: 300, opacity: 1 }}
  >
    {@render children()}
  </div>
</div>
