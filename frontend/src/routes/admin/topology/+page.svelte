<script lang="ts">
	import { onMount, untrack } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import GlobalTopology from '$lib/components/GlobalTopology.svelte';
	import InstanceDetailPanel from '$lib/components/InstanceDetailPanel.svelte';
	import RouterDetailPanel from '$lib/components/RouterDetailPanel.svelte';
	import SlidePanel from '$lib/components/SlidePanel.svelte';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import { projectNames } from '$lib/stores/projectNames';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import type { TopologyData, TopologyTraffic, TopologyLoadBalancer } from '$lib/types/topology';
	import ProjectFilter from '$lib/components/admin/topology/ProjectFilter.svelte';
	import TopologyLegend from '$lib/components/admin/topology/TopologyLegend.svelte';
	import TopologyLBPanel from '$lib/components/admin/topology/TopologyLBPanel.svelte';

	let isLight = $state(false);
	onMount(() => {
		isLight = document.documentElement.classList.contains('light');
		const obs = new MutationObserver(() => {
			isLight = document.documentElement.classList.contains('light');
		});
		obs.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
		return () => obs.disconnect();
	});

	let data = $state<TopologyData | null>(null);
	let traffic = $state<TopologyTraffic | null>(null);
	let loading = $state(true);
	let refreshing = $state(false);
	let error = $state('');
	let selectedInstanceId = $state<string | null>(null);
	let selectedRouterId = $state<string | null>(null);
	let selectedLB = $state<TopologyLoadBalancer | null>(null);

	// 토폴로지 선택 상태를 부모에서 파생
	const topologySelectedId = $derived(
		selectedInstanceId ?? selectedRouterId ?? selectedLB?.id ?? null
	);

	// 프로젝트 필터
	let projectFilter = $state<string | null>(null);
	let projectSearchText = $state('');
	let projectDropdownOpen = $state(false);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	function handleDocumentClick(e: MouseEvent) {
		const target = e.target as HTMLElement;
		if (!target.closest('.project-filter-wrapper')) {
			projectDropdownOpen = false;
		}
	}

	const ar = createAutoRefresh(fetchTopology, {
		storageKey: 'admin-topology',
		defaultActive: true,
		defaultInterval: 30,
		intervalOptions: [15, 30, 60]
	});

	async function loadTraffic() {
		if (!$auth.token) return;
		try {
			traffic = await api.get<TopologyTraffic>(
				'/api/networks/topology/traffic?all_projects=true',
				$auth.token ?? undefined,
				$auth.projectId ?? undefined,
			);
		} catch { /* silent — traffic=null 로 표시 유지 */ }
	}

	const arTraffic = createAutoRefresh(loadTraffic, {
		storageKey: 'admin-topology-traffic',
		defaultActive: true,
		defaultInterval: 15,
		intervalOptions: [10, 15, 30],
	});

	$effect(() => {
		if (!$auth.token) return;
		untrack(() => fetchTopology());
	});

	$effect(() => {
		if (!$auth.token) return;
		untrack(() => loadTraffic());
	});

	onMount(() => {
		projectNames.load(token, projectId);
		document.addEventListener('click', handleDocumentClick);
		return () => document.removeEventListener('click', handleDocumentClick);
	});

	async function fetchTopology() {
		if (!data) loading = true;
		else refreshing = true;
		error = '';
		try {
			data = await api.get<TopologyData>(
				'/api/admin/topology',
				$auth.token ?? undefined,
				$auth.projectId ?? undefined
			);
		} catch (e) {
			error = e instanceof ApiError ? `조회 실패 (${e.status}): ${e.message}` : '서버 오류';
		} finally {
			loading = false;
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
				refreshing={loading || refreshing}
				onManualRefresh={fetchTopology}
			/>
		{/snippet}
	</PageHeader>

	<!-- 프로젝트 필터 -->
	<div class="flex gap-3 mb-4">
		<ProjectFilter bind:projectFilter bind:searchText={projectSearchText} bind:dropdownOpen={projectDropdownOpen} />
	</div>

	{#if error}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">
			{error}
		</div>
	{:else if loading}
		<LoadingSkeleton variant="card" rows={8} />
	{:else if data}
		<div class:opacity-60={refreshing} class:pointer-events-none={refreshing}>
		<div class="bg-gray-900 border border-gray-800 rounded-lg p-6 mb-4">
			<GlobalTopology
				{data}
				{traffic}
				projectId={projectFilter}
				showAll={projectFilter == null}
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

		<TopologyLegend {isLight} />

		<!-- 전체 요약 -->
		<div class="mt-4 flex gap-6 text-xs text-gray-500 px-1">
			<span>네트워크 {data.networks.length}개</span>
			<span>라우터 {data.routers.length}개</span>
			<span>인스턴스 {data.instances.length}개</span>
			<span>Floating IP {data.floating_ips.length}개</span>
			<span>로드밸런서 {(data.load_balancers ?? []).length}개</span>
		</div>
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
		<TopologyLBPanel lb={selectedLB} onClose={() => selectedLB = null} />
	</SlidePanel>
{/if}
