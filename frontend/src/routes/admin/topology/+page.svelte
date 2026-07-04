<script lang="ts">
	import { onMount, untrack } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import { createAdminTopologyController } from '$lib/stores/adminTopologyController.svelte';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import GlobalTopology from '$lib/components/GlobalTopology.svelte';
	import InstanceDetailPanel from '$lib/components/InstanceDetailPanel.svelte';
	import RouterDetailPanel from '$lib/components/RouterDetailPanel.svelte';
	import SlidePanel from '$lib/components/SlidePanel.svelte';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import { projectNames } from '$lib/stores/projectNames';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
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

	const ctrl = createAdminTopologyController({
		token: () => $auth.token ?? undefined,
		projectId: () => $auth.projectId ?? undefined,
	});

	const ar = createAutoRefresh(ctrl.fetchTopology, {
		storageKey: 'admin-topology',
		defaultActive: true,
		defaultInterval: 30,
		intervalOptions: [15, 30, 60]
	});

	const arTraffic = createAutoRefresh(ctrl.loadTraffic, {
		storageKey: 'admin-topology-traffic',
		defaultActive: true,
		defaultInterval: 15,
		intervalOptions: [10, 15, 30],
	});

	$effect(() => {
		if (!$auth.token) return;
		untrack(() => ctrl.fetchTopology());
	});

	$effect(() => {
		if (!$auth.token) return;
		untrack(() => ctrl.loadTraffic());
	});

	onMount(() => {
		const token = $auth.token ?? undefined;
		const projectId = $auth.projectId ?? undefined;
		projectNames.load(token, projectId);
		document.addEventListener('click', ctrl.handleDocumentClick);
		return () => document.removeEventListener('click', ctrl.handleDocumentClick);
	});
</script>

<div class="p-4 md:p-8 max-w-screen-2xl mx-auto">
	<PageHeader breadcrumb="NETWORK / TOPOLOGY" title="토폴로지">
		{#snippet actions()}
			<AutoRefreshControl
				bind:active={ar.active}
				bind:intervalSeconds={ar.intervalSeconds}
				intervalOptions={ar.intervalOptions}
				refreshing={ctrl.loading || ctrl.refreshing}
				onManualRefresh={ctrl.fetchTopology}
			/>
		{/snippet}
	</PageHeader>

	<!-- 프로젝트 필터 -->
	<div class="flex gap-3 mb-4">
		<ProjectFilter bind:projectFilter={ctrl.projectFilter} bind:searchText={ctrl.projectSearchText} bind:dropdownOpen={ctrl.projectDropdownOpen} />
	</div>

	{#if ctrl.error}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">
			{ctrl.error}
		</div>
	{:else if ctrl.loading}
		<LoadingSkeleton variant="card" rows={8} />
	{:else if ctrl.data}
		<div class="bg-gray-900 border border-gray-800 rounded-lg p-6 mb-4">
			<GlobalTopology
				data={ctrl.data}
				traffic={ctrl.traffic}
				projectId={ctrl.projectFilter}
				showAll={ctrl.projectFilter == null}
				selectedId={ctrl.topologySelectedId}
				onSelectInstance={(id) => {
					if (ctrl.selectedInstanceId === id) { ctrl.selectedInstanceId = null; }
					else { ctrl.selectedInstanceId = id; ctrl.selectedRouterId = null; ctrl.selectedLB = null; }
				}}
				onSelectRouter={(id) => {
					if (ctrl.selectedRouterId === id) { ctrl.selectedRouterId = null; }
					else { ctrl.selectedRouterId = id; ctrl.selectedInstanceId = null; ctrl.selectedLB = null; }
				}}
				onSelectLoadBalancer={(lb) => {
					if (ctrl.selectedLB?.id === lb.id) { ctrl.selectedLB = null; }
					else { ctrl.selectedLB = lb; ctrl.selectedInstanceId = null; ctrl.selectedRouterId = null; }
				}}
			/>
		</div>

		<TopologyLegend {isLight} />

		<!-- 전체 요약 -->
		<div class="mt-4 flex gap-6 text-xs text-gray-500 px-1">
			<span>네트워크 {ctrl.data.networks.length}개</span>
			<span>라우터 {ctrl.data.routers.length}개</span>
			<span>인스턴스 {ctrl.data.instances.length}개</span>
			<span>Floating IP {ctrl.data.floating_ips.length}개</span>
			<span>로드밸런서 {(ctrl.data.load_balancers ?? []).length}개</span>
		</div>
	{/if}
</div>

{#if ctrl.selectedInstanceId}
	<SlidePanel onClose={() => ctrl.selectedInstanceId = null}>
		<InstanceDetailPanel instanceId={ctrl.selectedInstanceId} onClose={() => ctrl.selectedInstanceId = null} />
	</SlidePanel>
{/if}

{#if ctrl.selectedRouterId}
	<SlidePanel onClose={() => ctrl.selectedRouterId = null} width="w-full md:w-[60vw] max-w-3xl">
		<RouterDetailPanel routerId={ctrl.selectedRouterId} onClose={() => ctrl.selectedRouterId = null} />
	</SlidePanel>
{/if}

{#if ctrl.selectedLB}
	<SlidePanel onClose={() => ctrl.selectedLB = null} width="w-full md:w-[60vw] max-w-2xl">
		<TopologyLBPanel lb={ctrl.selectedLB} onClose={() => ctrl.selectedLB = null} />
	</SlidePanel>
{/if}
