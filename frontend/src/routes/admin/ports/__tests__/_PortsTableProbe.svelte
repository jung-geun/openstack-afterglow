<script lang="ts">
	let {
		ports = [],
	}: {
		ports?: Array<{ id: string; name?: string }>;
	} = $props();
</script>

{#each ports as port}
	<span>{port.name}</span>
{/each}
