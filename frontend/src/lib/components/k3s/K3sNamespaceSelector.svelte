<script lang="ts">
  import { useK3sClusterDetail } from '$lib/stores/k3sClusterDetail.svelte';
  import { untrack } from 'svelte';

  const s = useK3sClusterDetail();

  $effect(() => {
    if (s.isActive) {
      untrack(() => s.loadNamespaces());
    }
  });
</script>

<div class="flex items-center gap-2 mb-3">
  <span class="text-xs text-gray-500">네임스페이스</span>
  <select
    bind:value={s.selectedNamespace}
    onchange={() => { s.loadConfigMaps(); s.loadSecrets(); }}
    class="bg-gray-800 border border-gray-700 text-gray-200 text-xs rounded px-2 py-1 focus:outline-none focus:border-blue-500"
  >
    {#each s.namespaces.length > 0 ? s.namespaces : ['default'] as ns}
      <option value={ns}>{ns}</option>
    {/each}
  </select>
</div>
