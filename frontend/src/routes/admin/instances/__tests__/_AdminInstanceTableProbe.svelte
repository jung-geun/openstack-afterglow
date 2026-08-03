<script lang="ts">
	let {
		instances = [],
	}: {
		instances?: Array<{ id: string; name: string }>;
	} = $props();
</script>

{#each instances as instance}
	<span>{instance.name}</span>
{/each}
