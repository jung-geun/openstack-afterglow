<script lang="ts">
	import Sidebar from '$lib/components/Sidebar.svelte';
	let { children } = $props();
</script>

<div class="flex" style="min-height: calc(100vh - 3.5rem)">
	<Sidebar />
	<main class="flex-1 overflow-auto min-w-0">
		{@render children()}
	</main>
</div>
