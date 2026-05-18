<script lang="ts">
  import { goto } from '$app/navigation';
  import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
  import type { Cluster } from '$lib/types/cluster';
  import type { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';

  let {
    cluster,
    refreshing,
    ar,
    onManualRefresh,
    onDelete,
  }: {
    cluster: Cluster;
    refreshing: boolean;
    ar: ReturnType<typeof createAutoRefresh>;
    onManualRefresh: () => void;
    onDelete: () => void;
  } = $props();
</script>

<div class="flex items-center gap-3 mb-6">
  <button onclick={() => goto('/dashboard/containers/clusters')} class="text-gray-400 hover:text-white transition-colors text-sm">← 클러스터 목록</button>
</div>

<div class="flex items-start justify-between mb-4">
  <div>
    <h1 class="text-2xl font-bold text-white">{cluster.name}</h1>
    <p class="text-gray-500 text-sm mt-0.5 font-mono">ID: {cluster.id}</p>
    {#if cluster.stack_id}
      <p class="text-gray-600 text-xs mt-0.5 font-mono">Stack: {cluster.stack_id}</p>
    {/if}
  </div>
  <div class="flex items-center gap-2">
    <AutoRefreshControl
      bind:active={ar.active}
      bind:intervalSeconds={ar.intervalSeconds}
      intervalOptions={ar.intervalOptions}
      {refreshing}
      {onManualRefresh}
    />
    <button onclick={onDelete} class="px-4 py-1.5 text-sm text-red-400 border border-red-800 hover:bg-red-900/30 rounded-lg transition-colors">삭제</button>
  </div>
</div>
