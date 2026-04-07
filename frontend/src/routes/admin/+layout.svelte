<script lang="ts">
	import { goto } from '$app/navigation';
	import { isAdmin } from '$lib/stores/auth';
	import AdminSidebar from '$lib/components/AdminSidebar.svelte';

	$effect(() => {
		if (!$isAdmin) goto('/dashboard');
	});

	let { children } = $props();
</script>

<div class="flex" style="min-height: calc(100vh - 3.5rem)">
	<AdminSidebar />
	<main class="flex-1 overflow-auto min-w-0">
		{@render children()}
	</main>
</div>
