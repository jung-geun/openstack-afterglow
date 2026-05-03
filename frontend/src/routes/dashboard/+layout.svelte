<script lang="ts">
	import Sidebar from '$lib/components/Sidebar.svelte';
	import VmCreatePanel from '$lib/components/VmCreatePanel.svelte';
	import { wizardOpen } from '$lib/stores/wizard';
	let { children } = $props();
</script>

<div class="flex min-h-screen">
	<Sidebar />
	<main class="flex-1 overflow-auto min-w-0 pt-14">
		{@render children()}
	</main>
</div>

{#if $wizardOpen}
	<VmCreatePanel />
{/if}
