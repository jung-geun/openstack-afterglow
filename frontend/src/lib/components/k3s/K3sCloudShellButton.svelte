<script lang="ts">
  import { useK3sClusterDetailController } from '$lib/stores/k3sClusterDetailController.svelte';

  const s = useK3sClusterDetailController();
</script>

{#if s.isActive && s.kubeconfigAvailable}
  <button
    onclick={() => s.openShell()}
    class="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-200 text-xs rounded-lg transition-colors"
  >
    Cloud Shell
  </button>
{/if}
