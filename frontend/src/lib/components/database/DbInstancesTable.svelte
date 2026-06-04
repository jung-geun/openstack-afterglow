<script lang="ts">
  import type { DbInstance } from '$lib/types/database';
  import StatusChip from '$lib/components/ui/StatusChip.svelte';

  let {
    instances,
    refreshing,
    restarting,
    deleting,
    onOpen,
    onRestart,
    onDelete,
  }: {
    instances: DbInstance[];
    refreshing: boolean;
    restarting: string | null;
    deleting: string | null;
    onOpen: (id: string) => void;
    onRestart: (id: string, name: string) => Promise<void>;
    onDelete: (id: string, name: string) => Promise<void>;
  } = $props();
</script>

<div class="overflow-x-auto" class:opacity-60={refreshing} class:pointer-events-none={refreshing}>
  <table class="w-full text-sm">
    <thead>
      <tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
        <th class="text-left py-3 px-4 font-medium">이름</th>
        <th class="text-left py-3 px-4 font-medium">상태</th>
        <th class="text-left py-3 px-4 font-medium">Datastore</th>
        <th class="text-left py-3 px-4 font-medium">크기 (GB)</th>
        <th class="text-left py-3 px-4 font-medium">생성일</th>
        <th class="text-right py-3 px-4 font-medium">액션</th>
      </tr>
    </thead>
    <tbody>
      {#each instances as inst}
        <tr class="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
          <td class="py-3 px-4">
            <button onclick={() => onOpen(inst.id)} class="text-amber-400 hover:text-amber-300 font-medium text-left">
              {inst.name}
            </button>
          </td>
          <td class="py-3 px-4"><StatusChip status={inst.status} /></td>
          <td class="py-3 px-4 text-gray-300">{inst.datastore?.type ?? '-'} {inst.datastore?.version ?? ''}</td>
          <td class="py-3 px-4 text-gray-300">{inst.size || '-'}</td>
          <td class="py-3 px-4 text-gray-500 text-xs">{inst.created_at ? inst.created_at.slice(0, 10) : '-'}</td>
          <td class="py-3 px-4 text-right">
            <div class="flex justify-end gap-1">
              <button
                onclick={() => onRestart(inst.id, inst.name)}
                disabled={restarting === inst.id}
                class="text-blue-400 hover:text-blue-300 disabled:text-gray-600 text-xs px-2 py-1 rounded border border-blue-900 hover:border-blue-700 disabled:border-gray-700 transition-colors"
              >{restarting === inst.id ? '...' : '재시작'}</button>
              <button
                onclick={(e) => { e.stopPropagation(); onDelete(inst.id, inst.name); }}
                disabled={deleting === inst.id}
                class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-1 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors"
              >{deleting === inst.id ? '...' : '삭제'}</button>
            </div>
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>
