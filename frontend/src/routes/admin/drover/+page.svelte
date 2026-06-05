<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import { projectNames } from '$lib/stores/projectNames';
	import K3sClusterDetailPanel from '$lib/components/K3sClusterDetailPanel.svelte';
	import SlidePanel from '$lib/components/SlidePanel.svelte';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import StatusChip from '$lib/components/ui/StatusChip.svelte';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';

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

	let clusters = $state<AdminK3sCluster[]>([]);
	let loading = $state(true);
	let refreshing = $state(false);

	// 슬라이드 패널
	let selectedClusterId = $state<string | null>(null);

	function openClusterPanel(id: string) {
		selectedClusterId = id;
	}

	function closeClusterPanel() {
		selectedClusterId = null;
	}

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function load() {
		if (clusters.length === 0) loading = true;
		else refreshing = true;
		try {
			clusters = await api.get<AdminK3sCluster[]>('/api/admin/k3s-clusters', token, projectId);
		} catch {
			clusters = [];
		} finally {
			loading = false;
			refreshing = false;
		}
	}

	const ar = createAutoRefresh(load, {
		storageKey: 'admin-drover',
		defaultActive: true,
		defaultInterval: 15,
		intervalOptions: [10, 15, 30, 60]
	});

	onMount(() => {
		load();
		projectNames.load(token, projectId);
	});
</script>

<!-- 슬라이드 패널 -->
{#if selectedClusterId}
	<SlidePanel onClose={closeClusterPanel}>
		<K3sClusterDetailPanel clusterId={selectedClusterId} onClose={closeClusterPanel} adminMode={true} />
	</SlidePanel>
{/if}

<div class="p-4 md:p-8 max-w-7xl mx-auto">
	<PageHeader breadcrumb="DROVER" title="Drover 클러스터">
		{#snippet actions()}
			<AutoRefreshControl
				bind:active={ar.active}
				bind:intervalSeconds={ar.intervalSeconds}
				intervalOptions={ar.intervalOptions}
				refreshing={loading || refreshing}
				onManualRefresh={load}
			/>
		{/snippet}
	</PageHeader>

	{#if loading}
		<LoadingSkeleton variant="table" rows={5} />
	{:else if clusters.length === 0}
		<div class="text-gray-600 text-sm">Drover 클러스터가 없습니다</div>
	{:else}
		<div class="overflow-x-auto" class:opacity-60={refreshing} class:pointer-events-none={refreshing}>
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
						<tr
							class="border-b border-gray-800/50 text-xs hover:bg-gray-800/30 transition-colors cursor-pointer"
							onclick={() => openClusterPanel(c.id)}
							onkeydown={(e) => e.key === 'Enter' && openClusterPanel(c.id)}
							role="button"
							tabindex="0">
							<td class="py-2 pr-4">
								<span class="text-white hover:text-blue-400 transition-colors max-md:block max-md:max-w-[66vw] max-md:truncate" title={c.name}>
									{c.name}
								</span>
								{#if c.status_reason}
									<div class="text-gray-500 text-xs mt-0.5 truncate max-w-40">{c.status_reason}</div>
								{/if}
							</td>
							<td class="py-2 pr-4">
								<StatusChip status={c.status} />
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
