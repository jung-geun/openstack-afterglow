<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';

	interface DbInstance {
		id: string;
		name: string;
		status: string;
		datastore: { type?: string; version?: string };
		flavor_id: string;
		size: number;
		created_at: string;
	}

	const statusColor: Record<string, string> = {
		ACTIVE: 'text-green-400',
		BUILD: 'text-yellow-400',
		ERROR: 'text-red-400',
		SHUTDOWN: 'text-gray-400',
	};

	let instances = $state<DbInstance[]>([]);
	let loading = $state(true);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function load() {
		loading = true;
		try {
			instances = await api.get<DbInstance[]>('/api/database-instances', token, projectId);
		} catch {
			instances = [];
		} finally {
			loading = false;
		}
	}

	onMount(load);
</script>

<div class="p-4 md:p-8 max-w-6xl">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-white">DB 인스턴스</h1>
		<button onclick={load} class="text-xs text-gray-400 hover:text-white transition-colors px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600">새로고침</button>
	</div>

	{#if loading}
		<LoadingSkeleton variant="table" rows={5} />
	{:else if instances.length === 0}
		<div class="text-gray-600 text-sm">DB 인스턴스가 없습니다</div>
	{:else}
		<div class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
						<th class="text-left py-3 px-4 font-medium">이름</th>
						<th class="text-left py-3 px-4 font-medium">상태</th>
						<th class="text-left py-3 px-4 font-medium">Datastore</th>
						<th class="text-left py-3 px-4 font-medium">크기 (GB)</th>
						<th class="text-left py-3 px-4 font-medium">ID</th>
						<th class="text-left py-3 px-4 font-medium">생성일</th>
					</tr>
				</thead>
				<tbody>
					{#each instances as inst}
						<tr class="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
							<td class="py-3 px-4 text-white font-medium">{inst.name}</td>
							<td class="py-3 px-4 font-medium text-xs {statusColor[inst.status] ?? 'text-gray-300'}">{inst.status}</td>
							<td class="py-3 px-4 text-gray-300">{inst.datastore?.type ?? '-'} {inst.datastore?.version ?? ''}</td>
							<td class="py-3 px-4 text-gray-300">{inst.size || '-'}</td>
							<td class="py-3 px-4 text-gray-600 font-mono text-xs">{inst.id.slice(0, 8)}…</td>
							<td class="py-3 px-4 text-gray-500 text-xs">{inst.created_at ? inst.created_at.slice(0, 10) : '-'}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>
