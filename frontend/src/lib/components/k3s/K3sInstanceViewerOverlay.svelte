<script lang="ts">
  import { useK3sClusterDetail } from '$lib/stores/k3sClusterDetail.svelte';
  import InstanceDetailPanel from '$lib/components/InstanceDetailPanel.svelte';

  const s = useK3sClusterDetail();
</script>

<div class="absolute inset-0 z-10 bg-gray-950 overflow-y-auto">
  <div class="px-4 pt-4">
    <button
      onclick={() => s.clearViewingInstance()}
      class="text-gray-400 hover:text-white text-sm transition-colors mb-2">
      ← 클러스터 상세
    </button>
  </div>
  <InstanceDetailPanel instanceId={s.viewingInstanceId!} onClose={() => s.clearViewingInstance()} />
</div>
