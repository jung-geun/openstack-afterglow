<script lang="ts">
	import { untrack } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import GlobalTopology from '$lib/components/GlobalTopology.svelte';
	import InstanceDetailPanel from '$lib/components/InstanceDetailPanel.svelte';
	import RouterDetailPanel from '$lib/components/RouterDetailPanel.svelte';
	import SlidePanel from '$lib/components/SlidePanel.svelte';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import TopologyLegend from '$lib/components/dashboard/network/topology/TopologyLegend.svelte';
	import TopologySummary from '$lib/components/dashboard/network/topology/TopologySummary.svelte';
	import LoadBalancerDetailPanel from '$lib/components/dashboard/network/topology/LoadBalancerDetailPanel.svelte';
	import type { TopologyData, TopologyTraffic, TopologyLoadBalancer } from '$lib/types/topology';

	let data = $state<TopologyData | null>(null);
	let loading = $state(true);
	let refreshing = $state(false);
	let error = $state('');
	let traffic = $state<TopologyTraffic | null>(null);
	let selectedInstanceId = $state<string | null>(null);
	let selectedRouterId = $state<string | null>(null);
	let selectedLB = $state<TopologyLoadBalancer | null>(null);

	// 토폴로지 선택 상태를 부모에서 파생 (패널 닫을 때 자동 highlight 해제)
	const topologySelectedId = $derived(
		selectedInstanceId ?? selectedRouterId ?? selectedLB?.id ?? null
	);

	const ar = createAutoRefresh(() => fetchTopology(), {
		storageKey: 'dashboard-network-topology',
		defaultActive: true,
		defaultInterval: 30,
		intervalOptions: [10, 15, 30, 60],
	});

	async function loadTraffic() {
		if (!$auth.token) return;
		try {
			traffic = await api.get<TopologyTraffic>(
				'/api/networks/topology/traffic',
				$auth.token ?? undefined,
				$auth.projectId ?? undefined,
			);
		} catch { /* silent — 토폴로지 표시는 traffic=null 로 유지 */ }
	}

	const arTraffic = createAutoRefresh(loadTraffic, {
		storageKey: 'dashboard-network-topology-traffic',
		defaultActive: true,
		defaultInterval: 15,
		intervalOptions: [10, 15, 30],
	});

	$effect(() => {
		if (!$auth.token || !$auth.projectId) return;
		untrack(() => fetchTopology());
	});

	async function fetchTopology(opts?: { refresh?: boolean }) {
		if (!data) loading = true;
		else refreshing = true;
		error = '';
		try {
			data = await api.get<TopologyData>(
				'/api/networks/topology',
				$auth.token ?? undefined,
				$auth.projectId ?? undefined,
				opts,
			);
		} catch (e) {
			error = e instanceof ApiError ? `조회 실패 (${e.status}): ${e.message}` : '서버 오류';
		} finally {
			loading = false;
			refreshing = false;
		}
	}

	async function forceRefresh() {
		refreshing = true;
		try {
			await fetchTopology({ refresh: true });
		} finally {
			refreshing = false;
		}
	}
</script>

<div class="p-4 md:p-8 max-w-screen-2xl mx-auto">
	<PageHeader breadcrumb="NETWORK / TOPOLOGY" title="토폴로지">
		{#snippet actions()}
			<AutoRefreshControl
			bind:active={ar.active}
			bind:intervalSeconds={ar.intervalSeconds}
			intervalOptions={ar.intervalOptions}
			refreshing={refreshing || loading}
			onManualRefresh={forceRefresh}
		/>
		{/snippet}
	</PageHeader>

	{#if error}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">
			{error}
		</div>
	{:else if loading}
		<LoadingSkeleton variant="card" rows={8} />
	{:else if data}
		{@const _visibleNets = data.networks.filter(n => n.is_external || n.is_shared || n.project_id === $auth.projectId)}
		{@const _projectRouters = data.routers.filter(r => r.project_id === $auth.projectId)}
		{@const _projectFips = data.floating_ips.filter(f => !f.project_id || f.project_id === $auth.projectId)}
		{@const _projectLbs = (data.load_balancers ?? []).filter(lb => !lb.project_id || lb.project_id === $auth.projectId)}
		<div class:opacity-60={refreshing} class:pointer-events-none={refreshing}>
		<div class="bg-gray-900 border border-gray-800 rounded-lg p-6 mb-4">
			<GlobalTopology
				{data}
				{traffic}
				projectId={$auth.projectId}
				selectedId={topologySelectedId}
				onSelectInstance={(id) => {
					if (selectedInstanceId === id) { selectedInstanceId = null; }
					else { selectedInstanceId = id; selectedRouterId = null; selectedLB = null; }
				}}
				onSelectRouter={(id) => {
					if (selectedRouterId === id) { selectedRouterId = null; }
					else { selectedRouterId = id; selectedInstanceId = null; selectedLB = null; }
				}}
				onSelectLoadBalancer={(lb) => {
					if (selectedLB?.id === lb.id) { selectedLB = null; }
					else { selectedLB = lb; selectedInstanceId = null; selectedRouterId = null; }
				}}
			/>
		</div>

		<TopologyLegend />

		<TopologySummary
			visibleNetworkCount={_visibleNets.length}
			projectRouterCount={_projectRouters.length}
			instanceCount={data.instances.length}
			projectFipCount={_projectFips.length}
			projectLbCount={_projectLbs.length}
		/>
		</div>
	{/if}
</div>

{#if selectedInstanceId}
	<SlidePanel onClose={() => selectedInstanceId = null}>
		<InstanceDetailPanel instanceId={selectedInstanceId} onClose={() => selectedInstanceId = null} />
	</SlidePanel>
{/if}

{#if selectedRouterId}
	<SlidePanel onClose={() => selectedRouterId = null} width="w-full md:w-[60vw] max-w-3xl">
		<RouterDetailPanel routerId={selectedRouterId} onClose={() => selectedRouterId = null} />
	</SlidePanel>
{/if}

{#if selectedLB}
	<SlidePanel onClose={() => selectedLB = null} width="w-full md:w-[60vw] max-w-2xl">
		<LoadBalancerDetailPanel lb={selectedLB} onClose={() => selectedLB = null} />
	</SlidePanel>
{/if}
