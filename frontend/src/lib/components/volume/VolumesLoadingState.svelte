<script lang="ts">
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
</script>

<div class="grid grid-cols-3 gap-3.5 mb-5">
	{#each [1, 2, 3] as _}
		<div class="bg-gray-900 border border-gray-800 rounded-2xl p-5 animate-pulse">
			<div class="h-3 w-20 bg-gray-800 rounded mb-3"></div>
			<div class="h-8 w-16 bg-gray-800 rounded mb-3"></div>
			<div class="h-1.5 w-full bg-gray-800 rounded-full"></div>
		</div>
	{/each}
</div>
<LoadingSkeleton variant="table" rows={5} />
