<script lang="ts">
	import { page } from '$app/stores';
	import InstanceDetailPanel from '$lib/components/InstanceDetailPanel.svelte';

	const instanceId = $derived($page.params.id);
</script>

<div class="max-w-4xl mx-auto">
	<InstanceDetailPanel {instanceId} />
</div>
