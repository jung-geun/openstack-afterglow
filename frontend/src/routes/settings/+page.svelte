<script lang="ts">
	import { goto } from '$app/navigation';
	import SettingsModal from '$lib/components/SettingsModal.svelte';

	let open = $state(true);

	function handleClose() {
		open = false;
		goto('/dashboard');
	}
</script>

<SettingsModal {open} onclose={handleClose} />
