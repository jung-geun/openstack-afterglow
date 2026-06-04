<script lang="ts">
	import { page } from '$app/stores';
	import { auth } from '$lib/stores/auth';
	import ObjectBrowser from '$lib/components/ObjectBrowser.svelte';

	const containerName = $derived(decodeURIComponent($page.params.name ?? ''));
	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);
</script>

<ObjectBrowser mode="user" {containerName} {token} {projectId} />
