<script lang="ts">
  import { useK3sClusterDetailController } from '$lib/stores/k3sClusterDetailController.svelte';

  const s = useK3sClusterDetailController();
</script>

<div class="mb-4 bg-gray-900 border border-gray-700 rounded-xl p-4">
  <div class="flex items-center justify-between mb-2">
    <span class="text-sm text-gray-300">{s.deleteProgress!.msg}</span>
    <span class="text-xs text-gray-500">{s.deleteProgress!.pct}%</span>
  </div>
  <div class="bg-gray-800 rounded-full h-1.5">
    <div class="bg-red-500 h-1.5 rounded-full transition-all duration-500" style="width: {s.deleteProgress!.pct}%"></div>
  </div>
  {#if s.deleteProgress!.error}
    <p class="text-xs text-red-400 mt-2">{s.deleteProgress!.error}</p>
  {/if}
</div>
