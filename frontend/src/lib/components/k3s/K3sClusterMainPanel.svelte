<script lang="ts">
	import K3sClusterHeader from './K3sClusterHeader.svelte';
	import K3sDeleteProgress from './K3sDeleteProgress.svelte';
	import K3sClusterInfoCard from './K3sClusterInfoCard.svelte';
	import K3sClusterNodesCard from './K3sClusterNodesCard.svelte';
	import K3sClusterVmList from './K3sClusterVmList.svelte';
	import K3sNodegroupsSection from './K3sNodegroupsSection.svelte';
	import K3sClusterNetworksCard from './K3sClusterNetworksCard.svelte';
	import { useK3sClusterDetailController } from '$lib/stores/k3sClusterDetailController.svelte';

	const s = useK3sClusterDetailController();
</script>

<K3sClusterHeader />
{#if s.deleteProgress}<K3sDeleteProgress />{/if}
<div class="grid grid-cols-1 @3xl/panel:grid-cols-2 gap-3 mb-4">
	<K3sClusterInfoCard />
	<K3sClusterNodesCard />
</div>
<K3sClusterVmList />
<K3sNodegroupsSection />
<K3sClusterNetworksCard />
