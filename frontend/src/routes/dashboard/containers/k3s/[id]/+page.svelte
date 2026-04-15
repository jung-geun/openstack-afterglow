<script lang="ts">
  import { page } from '$app/stores';
  import K3sClusterDetailPanel from '$lib/components/K3sClusterDetailPanel.svelte';

  const clusterId = $derived($page.params.id);
</script>

<K3sClusterDetailPanel {clusterId} />
