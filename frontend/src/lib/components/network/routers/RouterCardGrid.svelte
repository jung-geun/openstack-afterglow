<script lang="ts">
  import type { Router } from '$lib/types/networks';
  import StatusChip from '$lib/components/ui/StatusChip.svelte';

  let {
    routers,
    externalNetworkName,
    onOpen,
  }: {
    routers: Router[];
    externalNetworkName: (id: string | null) => string;
    onOpen: (id: string) => void;
  } = $props();
</script>

<div class="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
  {#each routers as router (router.id)}
    <div
      class="bg-gray-900 border border-gray-800 rounded-2xl p-5 cursor-pointer hover:border-gray-600 transition-colors"
      onclick={() => onOpen(router.id)}
      role="button"
      tabindex="0"
      onkeydown={(e) => e.key === 'Enter' && onOpen(router.id)}
    >
      <div class="flex items-center gap-2.5 mb-3.5">
        <div class="w-10 h-10 rounded-[10px] bg-violet-500/15 border border-violet-500/30 text-violet-400 flex items-center justify-center shrink-0">
          <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"/>
            <line x1="2" y1="12" x2="22" y2="12"/>
            <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
          </svg>
        </div>
        <div class="flex-1 min-w-0">
          <div class="text-white text-[14px] font-semibold truncate">{router.name || router.id.slice(0, 12)}</div>
          <div class="text-[11px] text-gray-500 mt-0.5">SNAT {router.external_gateway_network_id ? '활성' : '비활성'}</div>
        </div>
        <StatusChip status={router.status} />
      </div>

      <div class="flex flex-col gap-2 text-[13px]">
        <div class="flex items-center gap-3 p-2.5 bg-[#0B1220] border border-gray-800 rounded-lg">
          <div class="text-[11px] uppercase tracking-wider font-medium text-gray-500 w-16 shrink-0">외부</div>
          {#if router.external_gateway_network_id}
            <div class="text-amber-400 font-mono text-xs truncate">{externalNetworkName(router.external_gateway_network_id)}</div>
          {:else}
            <div class="text-gray-600 text-xs">없음</div>
          {/if}
        </div>
        <div class="flex items-start gap-3 p-2.5 bg-[#0B1220] border border-gray-800 rounded-lg">
          <div class="text-[11px] uppercase tracking-wider font-medium text-gray-500 w-16 pt-0.5 shrink-0">내부</div>
          <div class="flex-1 flex flex-wrap gap-1.5">
            {#if router.connected_subnet_ids.length === 0}
              <span class="text-gray-600 text-xs">인터페이스 없음</span>
            {:else}
              {#each router.connected_subnet_ids as subnetId}
                <span class="px-1.5 py-0.5 bg-gray-800 border border-gray-700 rounded text-[10px] text-gray-400 font-mono">{subnetId.slice(0, 8)}…</span>
              {/each}
            {/if}
          </div>
        </div>
      </div>
    </div>
  {/each}
</div>
