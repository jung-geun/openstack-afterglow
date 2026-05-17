<script lang="ts">
  import { useK3sClusterDetail } from '$lib/stores/k3sClusterDetail.svelte';

  const s = useK3sClusterDetail();
</script>

{#if s.isActive && s.kubeconfigAvailable}
  <button
    onclick={() => s.openShell()}
    class="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-200 text-xs rounded-lg transition-colors"
  >
    Cloud Shell
  </button>
{/if}
