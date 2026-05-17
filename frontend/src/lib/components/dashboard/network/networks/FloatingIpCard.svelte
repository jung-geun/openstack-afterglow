<script lang="ts">
  import StatusChip from '$lib/components/ui/StatusChip.svelte';
  import type { FloatingIp } from '$lib/types/resources';

  let {
    floatingIps,
    hasExternalNetwork,
    onAllocateClick,
  }: {
    floatingIps: FloatingIp[];
    hasExternalNetwork: boolean;
    onAllocateClick: () => void;
  } = $props();
</script>

<div class="bg-gray-900 border border-gray-800 rounded-2xl p-5">
  <div class="flex items-center mb-3.5">
    <div class="text-white text-[15px] font-semibold">Floating IP</div>
    <div class="ml-auto flex gap-2">
      <button
        onclick={onAllocateClick}
        disabled={!hasExternalNetwork}
        class="px-3 py-1.5 text-[13px] bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white font-medium rounded-lg transition-colors"
        title={!hasExternalNetwork ? '외부 네트워크가 없습니다' : 'Floating IP 할당'}
      >+ Floating IP 할당</button>
    </div>
  </div>
  {#if floatingIps.length === 0}
    <div class="text-center py-8 text-gray-600 text-sm">Floating IP가 없습니다</div>
  {:else}
    <div class="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
      {#each floatingIps as fip (fip.id)}
        <div class="bg-[#0B1220] border border-gray-800 rounded-lg p-3 flex items-center gap-3">
          <div class="flex-1 min-w-0">
            <div class="font-mono text-[13px] text-white">{fip.floating_ip_address}</div>
            <div class="text-[11px] text-gray-500 mt-0.5 truncate">
              {fip.fixed_ip_address ? '→ ' + fip.fixed_ip_address : '미할당'}
            </div>
          </div>
          <StatusChip status={fip.status} />
        </div>
      {/each}
    </div>
  {/if}
</div>
