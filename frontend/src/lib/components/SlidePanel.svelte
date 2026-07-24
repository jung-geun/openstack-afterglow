<script lang="ts">
  import { fly, fade } from 'svelte/transition';
  import type { Snippet } from 'svelte';

  interface Props {
    onClose: () => void;
    width?: string;
    resizable?: boolean;
    storageKey?: string;
    dataTour?: string;
    children: Snippet;
  }

  let {
    onClose,
    width = 'w-full md:w-[75vw] max-w-5xl',
    resizable = true,
    storageKey,
    dataTour,
    children,
  }: Props = $props();

  const MIN_PX = 360;
  const SIDEBAR_WIDTH = 240;

  let widthPx = $state<number | null>(null);
  let panelEl = $state<HTMLElement | null>(null);
  let isDesktop = $state<boolean>(true);
  let viewportWidth = $state(typeof window === 'undefined' ? 0 : window.innerWidth);

  function maxPanelWidth(): number {
    return Math.max(MIN_PX, viewportWidth - SIDEBAR_WIDTH);
  }

  function clampPanelWidth(value: number): number {
    return Math.max(MIN_PX, Math.min(maxPanelWidth(), value));
  }

  function resolvedKey(): string {
    return storageKey ?? `slidePanel.${window.location.pathname}.width`;
  }

  $effect(() => {
    const mq = window.matchMedia('(min-width: 768px)');
    const update = () => {
      isDesktop = mq.matches;
      viewportWidth = window.innerWidth;
    };
    update();
    window.addEventListener('resize', update);
    mq.addEventListener('change', update);
    return () => {
      window.removeEventListener('resize', update);
      mq.removeEventListener('change', update);
    };
  });

  // 마운트 시 저장된 폭 복원
  $effect(() => {
    const saved = localStorage.getItem(resolvedKey());
    if (saved !== null) {
      const n = parseInt(saved, 10);
      if (!isNaN(n)) widthPx = n;
    }
  });

  // widthPx 변경 시 영속화
  $effect(() => {
    if (widthPx !== null) {
      localStorage.setItem(resolvedKey(), String(widthPx));
    }
  });

  function onHandleMouseDown(e: MouseEvent) {
    e.preventDefault();
    const startX = e.clientX;
    const startW = widthPx ?? panelEl?.offsetWidth ?? 600;
    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'col-resize';

    function onMove(ev: MouseEvent) {
      viewportWidth = window.innerWidth;
      widthPx = clampPanelWidth(startW + (startX - ev.clientX));
    }

    function onUp() {
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    }

    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }

  function onHandleDblClick() {
    widthPx = null;
    localStorage.removeItem(resolvedKey());
  }
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
    bind:this={panelEl}
    data-tour={dataTour}
    class="@container/panel absolute right-0 top-0 bottom-0 {width} bg-gray-950 border-l border-gray-700 overflow-y-auto shadow-2xl"
    style={isDesktop && widthPx !== null ? `width: ${clampPanelWidth(widthPx)}px; max-width: 100%` : ''}
    transition:fly={{ x: 400, duration: 300, opacity: 1 }}
  >
    {#if resizable}
      <!-- 폭 조정 핸들: 데스크톱에서만 노출, 더블클릭으로 기본값 리셋 -->
      <div
        class="absolute left-0 top-0 bottom-0 w-1 cursor-col-resize hover:bg-indigo-500/40 active:bg-indigo-500/60 z-10 hidden md:block"
        aria-hidden="true"
        onmousedown={onHandleMouseDown}
        ondblclick={onHandleDblClick}
      ></div>
    {/if}
    {@render children()}
  </div>
</div>
