<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { openWizard } from '$lib/stores/wizard';

	onMount(() => {
		openWizard();
		goto('/dashboard');
	});
</script>
