<script lang="ts">
  import StatusChip from '$lib/components/ui/StatusChip.svelte';
  import type { ShareNetwork } from '$lib/types/shareNetwork';

  let { networks, deleting, onDelete }: {
    networks: ShareNetwork[];
    deleting: string | null;
    onDelete: (id: string, name: string) => Promise<void>;
  } = $props();
</script>

<div class="overflow-x-auto">
  <table class="w-full text-sm">
    <thead>
      <tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
        <th class="text-left py-3 pr-6">이름</th>
        <th class="text-left py-3 pr-6">상태</th>
        <th class="text-left py-3 pr-6">Neutron 네트워크 ID</th>
        <th class="text-left py-3 pr-6">서브넷 ID</th>
        <th class="text-left py-3 pr-6">생성일</th>
        <th class="text-right py-3">액션</th>
      </tr>
    </thead>
    <tbody>
      {#each networks as net (net.id)}
        <tr class="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
          <td class="py-3 pr-6 font-medium text-white">
            {#if net.name}<span class="text-white font-medium max-md:block max-md:max-w-[66vw] max-md:truncate" title={net.name}>{net.name}</span>{:else}<span class="font-mono text-xs text-gray-400 max-md:block max-md:max-w-[66vw] max-md:truncate" title={net.id}>{net.id.slice(0, 8)}</span>{/if}
            {#if net.description}
              <div class="text-xs text-gray-500">{net.description}</div>
            {/if}
          </td>
          <td class="py-3 pr-6">
            <StatusChip status={net.status || null} />
          </td>
          <td class="py-3 pr-6 font-mono text-xs text-gray-400">{net.neutron_net_id?.slice(0, 20) ?? '-'}...</td>
          <td class="py-3 pr-6 font-mono text-xs text-gray-400">{net.neutron_subnet_id?.slice(0, 20) ?? '-'}...</td>
          <td class="py-3 pr-6 text-xs text-gray-500">{net.created_at ? net.created_at.split('T')[0] : '-'}</td>
          <td class="py-3 text-right">
            <button onclick={() => onDelete(net.id, net.name)}
              disabled={deleting === net.id}
              class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-1 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors">
              {deleting === net.id ? '삭제 중...' : '삭제'}
            </button>
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>
