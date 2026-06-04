<script lang="ts">
  import StatusChip from '$lib/components/ui/StatusChip.svelte';
  import ActionMenu from '$lib/components/ui/ActionMenu.svelte';
  import type { Network } from '$lib/types/networks';

  let {
    networks,
    defaultNetworkId,
    deleting,
    settingDefault,
    onOpenPanel,
    onSetDefault,
    onDelete,
  }: {
    networks: Network[];
    defaultNetworkId: string | null;
    deleting: string | null;
    settingDefault: string | null;
    onOpenPanel: (id: string) => void;
    onSetDefault: (id: string) => void;
    onDelete: (id: string, name: string, isExternal: boolean, isShared: boolean) => void;
  } = $props();

  let openNetMenu = $state<string | null>(null);

  $effect(() => {
    const close = () => { openNetMenu = null; };
    document.addEventListener('click', close);
    return () => document.removeEventListener('click', close);
  });
</script>

<div class="bg-gray-900 border border-gray-800 rounded-2xl p-5">
  <div class="text-white text-[15px] font-semibold mb-3.5">네트워크</div>
  <div class="bg-[#0B1220] border border-gray-800 rounded-[10px] overflow-hidden">
    <!-- Header -->
    <div class="grid grid-cols-[1fr_0px_auto_0px_0px_0px_0px] sm:grid-cols-[1.4fr_1fr_100px_80px_80px_100px_56px] px-4 py-2.5 border-b border-gray-800 text-[11px] uppercase tracking-wider text-gray-500 font-medium">
      <div>이름</div>
      <div class="hidden sm:block">CIDR</div>
      <div>유형</div>
      <div class="hidden sm:block">서브넷</div>
      <div class="hidden sm:block">MTU</div>
      <div class="hidden sm:block">상태</div>
      <div class="hidden sm:block"></div>
    </div>
    <!-- Rows -->
    {#each networks as net (net.id)}
      <div
        class="grid grid-cols-[1fr_0px_auto_0px_0px_0px_0px] sm:grid-cols-[1.4fr_1fr_100px_80px_80px_100px_56px] px-4 py-3 text-[13px] items-center border-b border-gray-800 transition-colors last:border-b-0"
      >
        <!-- 이름 -->
        <div class="flex items-center gap-2.5 min-w-0">
          <div class="shrink-0 w-7 h-7 rounded-md bg-violet-500/15 border border-violet-500/30 flex items-center justify-center">
            <svg class="w-3.5 h-3.5 text-violet-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div class="min-w-0">
            <div class="flex items-center gap-1.5">
              <button type="button" onclick={() => onOpenPanel(net.id)} class="font-medium text-white hover:text-blue-400 transition-colors text-left truncate">{net.name || net.id.slice(0, 12)}</button>
              {#if net.id === defaultNetworkId}
                <span class="text-[10px] px-1.5 py-0.5 rounded bg-blue-900/40 border border-blue-700/60 text-blue-400 shrink-0">기본</span>
              {/if}
            </div>
            <div class="text-[11px] text-gray-500 font-mono truncate">{net.id.slice(0, 8)}…</div>
          </div>
        </div>
        <!-- CIDR -->
        <div class="hidden sm:block text-gray-400 font-mono text-[12px]">—</div>
        <!-- 유형 badge -->
        <div>
          {#if net.is_external}
            <span class="text-[11px] px-2 py-0.5 rounded-md bg-amber-900/25 border border-amber-800 text-amber-400">외부</span>
          {:else if net.is_shared}
            <span class="text-[11px] px-2 py-0.5 rounded-md bg-teal-500/15 border border-teal-500/30 text-teal-400">공유</span>
          {:else}
            <span class="text-[11px] px-2 py-0.5 rounded-md bg-gray-800 border border-gray-700 text-gray-300">내부</span>
          {/if}
        </div>
        <!-- 서브넷 -->
        <div class="hidden sm:block text-gray-400 text-[12px]">{net.subnets.length}개</div>
        <!-- MTU -->
        <div class="hidden sm:block text-gray-500 font-mono text-[12px]">—</div>
        <!-- 상태 -->
        <div class="hidden sm:block"><StatusChip status={net.status} /></div>
        <!-- 액션 -->
        <div class="hidden sm:flex items-center justify-end" role="none">
          {#if !net.is_external && !net.is_shared}
            <ActionMenu
              open={openNetMenu === net.id}
              onopen={() => { openNetMenu = net.id; }}
              onclose={() => { openNetMenu = null; }}
            >
              {#if net.id !== defaultNetworkId}
                <button
                  onclick={() => { openNetMenu = null; onSetDefault(net.id); }}
                  disabled={settingDefault === net.id}
                  class="w-full text-left px-3 py-1.5 text-xs text-blue-400 hover:bg-gray-800 hover:text-blue-300 disabled:text-gray-600"
                >{settingDefault === net.id ? '설정 중...' : '기본 네트워크로 설정'}</button>
              {/if}
              <div class="border-t border-gray-800 my-1"></div>
              <button
                onclick={() => { openNetMenu = null; onDelete(net.id, net.name, net.is_external, net.is_shared); }}
                disabled={deleting === net.id}
                class="w-full text-left px-3 py-1.5 text-xs text-red-400 hover:bg-gray-800 hover:text-red-300 disabled:text-gray-600"
              >{deleting === net.id ? '삭제 중...' : '삭제'}</button>
            </ActionMenu>
          {/if}
        </div>
      </div>
    {/each}
  </div>
</div>
