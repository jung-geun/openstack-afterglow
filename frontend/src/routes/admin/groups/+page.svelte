<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';

	interface Group {
		id: string;
		name: string;
		description: string;
		domain_id: string | null;
	}

	let groups = $state<Group[]>([]);
	let loading = $state(true);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function load() {
		loading = true;
		try { groups = await api.get<Group[]>('/api/admin/groups', token, projectId); }
		catch { groups = []; }
		finally { loading = false; }
	}

	onMount(load);
</script>

<div class="p-4 md:p-8 max-w-6xl">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-white">그룹 관리</h1>
		<button onclick={load} class="text-xs text-gray-400 hover:text-white transition-colors px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600">새로고침</button>
	</div>

	{#if loading}
		<LoadingSkeleton variant="table" rows={5} />
	{:else if groups.length === 0}
		<div class="text-gray-600 text-sm">그룹이 없습니다</div>
	{:else}
		<div class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
						<th class="text-left py-2 pr-4">이름</th>
						<th class="text-left py-2 pr-4">설명</th>
						<th class="text-left py-2">ID</th>
					</tr>
				</thead>
				<tbody>
					{#each groups as g (g.id)}
						<tr class="border-b border-gray-800/50 text-xs">
							<td class="py-2 pr-4 text-white">{g.name}</td>
							<td class="py-2 pr-4 text-gray-400">{g.description || '-'}</td>
							<td class="py-2 text-gray-500 font-mono">{g.id.slice(0, 8)}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>