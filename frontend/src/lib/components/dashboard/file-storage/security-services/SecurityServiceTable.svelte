<script lang="ts">
  import StatusChip from '$lib/components/ui/StatusChip.svelte';
  import type { SecurityService } from '$lib/types/securityService';
  import { typeLabel } from '$lib/types/securityService';

  let {
    services,
    deleting,
    onAttachClick,
    onDelete,
    onCreateClick,
  }: {
    services: SecurityService[];
    deleting: string | null;
    onAttachClick: (id: string) => void;
    onDelete: (id: string, name: string) => void;
    onCreateClick: () => void;
  } = $props();
</script>

{#if services.length === 0}
  <div class="text-center py-20 text-gray-600">
    <div class="text-5xl mb-4">🔐</div>
    <p class="text-lg">Security Service가 없습니다</p>
    <button onclick={onCreateClick} class="text-blue-400 hover:text-blue-300 text-sm mt-2 inline-block">
      Security Service를 생성하세요 →
    </button>
  </div>
{:else}
  <div class="overflow-x-auto">
    <table class="w-full text-sm">
      <thead>
        <tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
          <th class="text-left py-3 pr-4">이름</th>
          <th class="text-left py-3 pr-4">유형</th>
          <th class="text-left py-3 pr-4">상태</th>
          <th class="text-left py-3 pr-4">DNS IP</th>
          <th class="text-left py-3 pr-4">서버</th>
          <th class="text-left py-3 pr-4">도메인</th>
          <th class="text-right py-3">액션</th>
        </tr>
      </thead>
      <tbody>
        {#each services as svc (svc.id)}
          <tr class="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
            <td class="py-3 pr-4 font-medium text-white">
              {svc.name}
              {#if svc.description}
                <div class="text-xs text-gray-500">{svc.description}</div>
              {/if}
            </td>
            <td class="py-3 pr-4">
              <span class="px-2 py-0.5 rounded text-xs bg-purple-900/30 text-purple-300">
                {typeLabel[svc.type] ?? svc.type}
              </span>
            </td>
            <td class="py-3 pr-4">
              <StatusChip status={svc.status || null} />
            </td>
            <td class="py-3 pr-4 text-xs text-gray-400 font-mono">{svc.dns_ip || '-'}</td>
            <td class="py-3 pr-4 text-xs text-gray-400">{svc.server || '-'}</td>
            <td class="py-3 pr-4 text-xs text-gray-400">{svc.domain || '-'}</td>
            <td class="py-3 text-right">
              <div class="flex justify-end gap-1">
                <button onclick={() => onAttachClick(svc.id)}
                  class="text-blue-400 hover:text-blue-300 text-xs px-2 py-1 rounded border border-blue-900 hover:border-blue-700 transition-colors">
                  네트워크 연결
                </button>
                <button onclick={() => onDelete(svc.id, svc.name)}
                  disabled={deleting === svc.id}
                  class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-1 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors">
                  {deleting === svc.id ? '삭제 중...' : '삭제'}
                </button>
              </div>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}
