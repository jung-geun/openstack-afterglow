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

<!-- main 영역(헤더 z-50 아래 + sidebar 우측)만 덮음. 헤더/sidebar 는 항상 보여 다른 페이지 navigation 가능.
     fixed top-14 left-0 md:left-60 right-0 bottom-0 — viewport 기준이지만 헤더(56px) 와 sidebar(60=240px) 영역 제외. -->
<div class="fixed top-14 left-0 md:left-60 right-0 bottom-0 z-40" role="dialog" aria-modal="true"
     onkeydown={(e) => e.key === 'Escape' && onClose()} tabindex="-1">
  <button
    class="absolute inset-0 bg-black/50 cursor-default"
    transition:fade={{ duration: 200 }}
    onclick={onClose}
    aria-label="패널 닫기"
  ></button>
  <div
    class="absolute right-0 top-0 bottom-0 {width} bg-gray-950 border-l border-gray-700 overflow-y-auto shadow-2xl"
    transition:fly={{ x: 400, duration: 300, opacity: 1 }}
  >
    {@render children()}
  </div>
</div>
