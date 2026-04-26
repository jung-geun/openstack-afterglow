<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';

	interface Role {
		id: string;
		name: string;
		domain_id: string | null;
	}

	let roles = $state<Role[]>([]);
	let loading = $state(true);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function load() {
		loading = true;
		try { roles = await api.get<Role[]>('/api/admin/roles', token, projectId); }
		catch { roles = []; }
		finally { loading = false; }
	}

	const ar = createAutoRefresh(load, {
		storageKey: 'admin-roles',
		defaultActive: true,
		defaultInterval: 60,
		intervalOptions: [30, 60]
	});

	onMount(load);
</script>

<div class="p-4 md:p-8 max-w-6xl">
	<PageHeader breadcrumb="IDENTITY / ROLES" title="역할">
		{#snippet actions()}
			<AutoRefreshControl
				bind:active={ar.active}
				bind:intervalSeconds={ar.intervalSeconds}
				intervalOptions={ar.intervalOptions}
				refreshing={loading}
				onManualRefresh={load}
			/>
		{/snippet}
	</PageHeader>

	{#if loading}
		<LoadingSkeleton variant="table" rows={5} />
	{:else if roles.length === 0}
		<div class="text-gray-600 text-sm">역할이 없습니다</div>
	{:else}
		<div class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
						<th class="text-left py-2 pr-4">이름</th>
						<th class="text-left py-2">ID</th>
					</tr>
				</thead>
				<tbody>
					{#each roles as r (r.id)}
						<tr class="border-b border-gray-800/50 text-xs">
							<td class="py-2 pr-4 text-white">{r.name}</td>
							<td class="py-2 text-gray-500 font-mono">{r.id.slice(0, 8)}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>