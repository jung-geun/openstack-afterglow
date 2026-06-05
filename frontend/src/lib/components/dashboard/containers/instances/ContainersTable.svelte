<script lang="ts">
  import { goto } from '$app/navigation';
  import StatusChip from '$lib/components/ui/StatusChip.svelte';
  import type { ZunContainer } from '$lib/types/zunContainer';

  interface Props {
    containers: ZunContainer[];
    actionTarget: string | null;
    onStart: (id: string) => Promise<void>;
    onStop: (id: string) => Promise<void>;
    onDelete: (id: string, name: string) => Promise<void>;
  }
  let { containers, actionTarget, onStart, onStop, onDelete }: Props = $props();
</script>

{#if containers.length === 0}
  <div class="text-center py-20 text-gray-600">
    <p class="text-lg mb-2">컨테이너가 없습니다</p>
    <p class="text-sm">Zun을 통해 새 컨테이너를 생성하세요</p>
  </div>
{:else}
  <div class="overflow-x-auto">
    <table class="w-full text-sm">
      <thead>
        <tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
          <th class="text-left py-3 pr-6">이름</th>
          <th class="text-left py-3 pr-6">상태</th>
          <th class="text-left py-3 pr-6">이미지</th>
          <th class="text-left py-3 pr-6">CPU</th>
          <th class="text-left py-3 pr-6">메모리</th>
          <th class="text-left py-3 pr-6">생성일</th>
          <th class="text-left py-3"></th>
        </tr>
      </thead>
      <tbody>
        {#each containers as c (c.uuid)}
          <tr class="border-b border-gray-800/50 hover:bg-gray-800/50 transition-colors">
            <td class="py-3 pr-6">
              <button onclick={() => goto(`/dashboard/containers/instances/${c.uuid}`)} class="font-medium text-white hover:text-blue-400 transition-colors text-left max-md:block max-md:max-w-[66vw] max-md:truncate" title={c.name}>{c.name}</button>
            </td>
            <td class="py-3 pr-6">
              <StatusChip status={c.status} />
            </td>
            <td class="py-3 pr-6 text-gray-400 text-xs font-mono">{c.image ?? '-'}</td>
            <td class="py-3 pr-6 text-gray-400 text-xs">{c.cpu ?? '-'}</td>
            <td class="py-3 pr-6 text-gray-400 text-xs">{c.memory ?? '-'}</td>
            <td class="py-3 pr-6 text-gray-400 text-xs">{c.created_at?.slice(0, 10) ?? '-'}</td>
            <td class="py-3">
              <div class="flex items-center gap-2">
                {#if c.status === 'Running'}
                  <button onclick={() => onStop(c.uuid)} disabled={actionTarget === c.uuid} class="text-xs text-orange-400 hover:text-orange-300 disabled:opacity-40 transition-colors">중지</button>
                {:else if c.status === 'Stopped' || c.status === 'Created'}
                  <button onclick={() => onStart(c.uuid)} disabled={actionTarget === c.uuid} class="text-xs text-green-400 hover:text-green-300 disabled:opacity-40 transition-colors">시작</button>
                {/if}
                <button onclick={() => onDelete(c.uuid, c.name)} disabled={actionTarget === c.uuid} class="text-xs text-red-400 hover:text-red-300 disabled:opacity-40 transition-colors">삭제</button>
              </div>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}
