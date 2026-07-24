<script lang="ts">
	let {
		volumes = [],
	}: {
		volumes?: Array<{ id: string; name: string }>;
	} = $props();
</script>

{#each volumes as volume}
	<span>{volume.name}</span>
{/each}
