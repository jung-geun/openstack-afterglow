<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import { projectNames } from '$lib/stores/projectNames';

	interface AdminK3sCluster {
		id: string;
		name: string;
		status: string;
		status_reason: string | null;
		server_ip: string | null;
		api_address: string | null;
		agent_count: number;
		agent_vm_ids: string[];
		k3s_version: string | null;
		created_at: string | null;
		project_id: string | null;
	}

	const statusColor: Record<string, string> = {
		ACTIVE:       'text-green-400',
		CREATING:     'text-yellow-400',
		PROVISIONING: 'text-blue-400',
		DELETING:     'text-orange-400',
		ERROR:        'text-red-400',
	};

	let clusters = $state<AdminK3sCluster[]>([]);
	let loading = $state(true);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function load() {
		loading = true;
		try {
			clusters = await api.get<AdminK3sCluster[]>('/api/admin/k3s-clusters', token, projectId);
		} catch {
			clusters = [];
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		load();
		projectNames.load(token, projectId);
	});
</script>

<div class="p-4 md:p-8 max-w-7xl">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-white">k3s 클러스터 (전체)</h1>
		<button onclick={load} class="text-xs text-gray-400 hover:text-white transition-colors px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600">새로고침</button>
	</div>

	{#if loading}
		<LoadingSkeleton variant="table" rows={5} />
	{:else if clusters.length === 0}
		<div class="text-gray-600 text-sm">k3s 클러스터가 없습니다</div>
	{:else}
		<div class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
						<th class="text-left py-2 pr-4">이름</th>
						<th class="text-left py-2 pr-4">상태</th>
						<th class="text-left py-2 pr-4">프로젝트</th>
						<th class="text-left py-2 pr-4">서버 IP</th>
						<th class="text-left py-2 pr-4">노드</th>
						<th class="text-left py-2 pr-4">버전</th>
						<th class="text-left py-2">생성일</th>
					</tr>
				</thead>
				<tbody>
					{#each clusters as c (c.id)}
						<tr class="border-b border-gray-800/50 text-xs hover:bg-gray-800/30 transition-colors">
							<td class="py-2 pr-4">
								<a href="/dashboard/containers/k3s/{c.id}" target="_blank" class="text-white hover:text-blue-400 transition-colors">
									{c.name}
								</a>
								{#if c.status_reason}
									<div class="text-gray-500 text-xs mt-0.5 truncate max-w-40">{c.status_reason}</div>
								{/if}
							</td>
							<td class="py-2 pr-4 {statusColor[c.status] ?? 'text-gray-400'}">
								{#if c.status === 'CREATING' || c.status === 'PROVISIONING'}
									<span class="animate-pulse">●</span>
								{/if}
								{c.status}
							</td>
							<td class="py-2 pr-4 text-gray-400">
								{c.project_id ? ($projectNames.get(c.project_id) ?? c.project_id.slice(0, 8)) : '-'}
							</td>
							<td class="py-2 pr-4 text-gray-400 font-mono">{c.server_ip || '-'}</td>
							<td class="py-2 pr-4 text-gray-400">1 서버 + {c.agent_vm_ids?.length ?? 0} / {c.agent_count} 에이전트</td>
							<td class="py-2 pr-4 text-gray-500">{c.k3s_version || '-'}</td>
							<td class="py-2 text-gray-500">{c.created_at ? c.created_at.slice(0, 10) : '-'}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>
