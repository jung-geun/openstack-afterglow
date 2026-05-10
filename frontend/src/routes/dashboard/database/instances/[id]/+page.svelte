<script lang="ts">
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { auth } from '$lib/stores/auth';
	import DbInstanceDetailPanel from '$lib/components/database/DbInstanceDetailPanel.svelte';

	const instanceId = $derived($page.params.id ?? '');
	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);
</script>

<div class="p-4 md:p-8 max-w-4xl">
	<!-- breadcrumb -->
	<div class="flex items-center gap-2 mb-4">
		<a href="/dashboard/database/instances" class="text-gray-500 hover:text-gray-300 text-sm">DB 인스턴스</a>
		<span class="text-gray-700">/</span>
		<span class="text-white text-sm font-medium">{instanceId.slice(0, 8)}...</span>
	</div>

	<DbInstanceDetailPanel
		{instanceId}
		{token}
		{projectId}
		onDeleted={() => goto('/dashboard/database/instances')}
	/>
</div>
