<script lang="ts">
  import type { StackResource } from '$lib/types/cluster';

  let { resources, isInProgress }: { resources: StackResource[]; isInProgress: boolean } = $props();

  const progressPct = $derived(
    resources.length === 0
      ? 0
      : Math.round(resources.filter(r => r.resource_status.endsWith('_COMPLETE')).length / resources.length * 100)
  );
</script>

{#if isInProgress && resources.length > 0}
  <div class="bg-gray-900 border border-gray-800 rounded-xl p-4 mb-4">
    <div class="flex items-center justify-between mb-2 text-sm">
      <span class="text-gray-400">배포 진행률</span>
      <span class="text-white font-medium">{progressPct}%</span>
    </div>
    <div class="w-full bg-gray-800 rounded-full h-2">
      <div class="bg-blue-500 h-2 rounded-full transition-all duration-500" style="width:{progressPct}%"></div>
    </div>
    <div class="text-xs text-gray-500 mt-1">
      {resources.filter(r => r.resource_status.endsWith('_COMPLETE')).length} / {resources.length} 리소스 완료
    </div>
  </div>
{/if}
