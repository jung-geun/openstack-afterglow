<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import TimeSeriesChart from '$lib/components/TimeSeriesChart.svelte';
	import InstanceDetailPanel from '$lib/components/InstanceDetailPanel.svelte';
	import SlidePanel from '$lib/components/SlidePanel.svelte';
	import { projectNames } from '$lib/stores/projectNames';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import { openWizard } from '$lib/stores/wizard';
	import AdminInstanceFilters from '$lib/components/admin/instances/AdminInstanceFilters.svelte';
	import AdminInstanceTable from '$lib/components/admin/instances/AdminInstanceTable.svelte';
	import type { AdminInstance, PagedResponse, TsPoint } from '$lib/types/adminInstance';

	let allInstances = $state<AdminInstance[]>([]);
	let loading = $state(true);
	let refreshing = $state(false);
	let pageSize = $state(20);
	let markerStack = $state<string[]>([]);
	let nextMarker = $state<string | null>(null);
	let availableHosts = $state<string[]>([]);
	let hostFilter = $state('');
	let statusFilter = $state('');
	let nameSearch = $state('');
	let projectFilter = $state('');
	let projectSearchText = $state('');
	let tsData = $state<TsPoint[]>([]);
	let tsRange = $state('7d');
	let tsLoading = $state(true);
	let selectedInstanceId = $state<string | null>(null);
	let selectedProjectId = $state<string | null>(null);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function load(marker?: string) {
		allInstances.length === 0 ? (loading = true) : (refreshing = true);
		try {
			let url = `/api/admin/all-instances?limit=${pageSize}`;
			if (marker) url += `&marker=${marker}`;
			if (hostFilter) url += `&host=${encodeURIComponent(hostFilter)}`;
			if (projectFilter) url += `&project_id=${encodeURIComponent(projectFilter)}`;
			if (statusFilter) url += `&status=${encodeURIComponent(statusFilter)}`;
			if (nameSearch) url += `&name=${encodeURIComponent(nameSearch)}`;
			const res = await api.get<PagedResponse<AdminInstance>>(url, token, projectId);
			allInstances = res.items;
			nextMarker = res.next_marker;
		} catch { allInstances = []; }
		finally { loading = false; refreshing = false; }
	}

	async function loadHosts() {
		try {
			const hvs = await api.get<{ id: string; name: string }[]>('/api/admin/hypervisors', token, projectId);
			availableHosts = hvs.map(h => h.name).sort();
		} catch { availableHosts = []; }
	}

	async function loadTimeseries(range: string) {
		tsLoading = true;
		try { tsData = await api.get<TsPoint[]>(`/api/admin/timeseries/instances?range=${range}`, token, projectId); }
		catch { tsData = []; }
		finally { tsLoading = false; }
	}

	function openDetail(inst: AdminInstance) { selectedInstanceId = inst.id; selectedProjectId = inst.project_id; }
	function closeDetail() { selectedInstanceId = null; selectedProjectId = null; }
	function onFilterChange() { markerStack = []; nextMarker = null; load(); }
	function onPrev() {
		const prev = markerStack.slice(0, -1);
		markerStack = prev;
		load(prev[prev.length - 1]);
	}
	function onNext() { if (!nextMarker) return; markerStack = [...markerStack, nextMarker]; load(nextMarker); }

	const ar = createAutoRefresh(
		() => { load(markerStack[markerStack.length - 1]); loadTimeseries(tsRange); },
		{ storageKey: 'admin-instances', defaultActive: true, defaultInterval: 15, intervalOptions: [10, 15, 30, 60] }
	);

	onMount(() => { load(); loadTimeseries(tsRange); loadHosts(); projectNames.load(token, projectId); });
</script>

<div class="p-4 md:p-8 max-w-7xl mx-auto">
	<PageHeader breadcrumb="COMPUTE / INSTANCES" title="전체 인스턴스">
		{#snippet actions()}
			<button
				onclick={() => openWizard()}
				class="px-3 py-1.5 text-sm font-medium bg-blue-600 hover:bg-blue-500 text-white rounded-lg transition-colors flex items-center gap-1.5"
			>
				<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
				</svg>
				VM 생성
			</button>
			<AutoRefreshControl
				bind:active={ar.active}
				bind:intervalSeconds={ar.intervalSeconds}
				intervalOptions={ar.intervalOptions}
				refreshing={loading || refreshing}
				onManualRefresh={() => { markerStack = []; nextMarker = null; hostFilter = ''; projectFilter = ''; projectSearchText = ''; statusFilter = ''; nameSearch = ''; load(); loadHosts(); }}
			/>
			<div class="flex items-center gap-1 text-xs text-gray-500">
				표시:
				{#each [10, 20, 30] as n}
					<button
						onclick={() => { pageSize = n; markerStack = []; nextMarker = null; load(); }}
						class="px-2 py-0.5 rounded {pageSize === n ? 'bg-blue-600 text-white' : 'bg-gray-800 hover:bg-gray-700 text-gray-400'}"
					>{n}</button>
				{/each}
			</div>
		{/snippet}
	</PageHeader>

	<AdminInstanceFilters
		{availableHosts}
		bind:hostFilter
		bind:statusFilter
		bind:nameSearch
		bind:projectFilter
		bind:projectSearchText
		onChange={onFilterChange}
	/>

	<div class="mb-6">
		{#if tsLoading}
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-5 h-48 flex items-center justify-center">
				<div class="text-gray-600 text-sm">차트 로딩 중...</div>
			</div>
		{:else}
			<TimeSeriesChart
				data={tsData}
				title="인스턴스 수 추이"
				mainKey="total"
				extraKeys={['active', 'shutoff', 'error', 'shelved']}
				currentRange={tsRange}
				onRangeChange={(r) => { tsRange = r; loadTimeseries(r); }}
			/>
		{/if}
	</div>

	{#if loading}
		<LoadingSkeleton variant="table" rows={5} />
	{:else}
		<AdminInstanceTable
			instances={allInstances}
			{markerStack}
			{nextMarker}
			{refreshing}
			onOpen={openDetail}
			{onPrev}
			{onNext}
		/>
	{/if}
</div>

{#if selectedInstanceId}
	<SlidePanel onClose={closeDetail}>
		<InstanceDetailPanel instanceId={selectedInstanceId} adminProjectId={selectedProjectId} onClose={closeDetail} />
	</SlidePanel>
{/if}
