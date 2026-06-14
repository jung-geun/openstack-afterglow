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
	import { toast } from '$lib/stores/toast';
	import { confirmDialog } from '$lib/stores/confirm.svelte';
	import { isTransitional } from '$lib/utils/instanceStatus';
	import RecoveryModal from '$lib/components/admin/instances/RecoveryModal.svelte';
	import type { AdminInstance, PagedResponse, TsPoint } from '$lib/types/adminInstance';
	import { StatTile } from '$lib/components/ui';

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

	interface InstanceHealth {
		total: number;
		active: number;
		error: number;
		with_alerts: number;
		gpu_count: number;
	}
	let health = $state<InstanceHealth | null>(null);

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

	async function loadTimeseries(range: string, opts?: { background?: boolean }) {
		if (!opts?.background) tsLoading = true;
		try { tsData = await api.get<TsPoint[]>(`/api/admin/timeseries/instances?range=${range}`, token, projectId); }
		catch { if (!opts?.background) tsData = []; }
		finally { if (!opts?.background) tsLoading = false; }
	}

	async function loadHealth() {
		try {
			health = await api.get<InstanceHealth>('/api/admin/instances/health', token, projectId);
		} catch { health = null; }
	}

	let selectedIds = $state(new Set<string>());
	let bulkActioning = $state(false);
	let recoveryInst = $state<AdminInstance | null>(null);

	function openDetail(inst: AdminInstance) { selectedInstanceId = inst.id; selectedProjectId = inst.project_id; }
	function closeDetail() { selectedInstanceId = null; selectedProjectId = null; }
	function openRecovery(inst: AdminInstance) { recoveryInst = inst; }
	function closeRecovery() { recoveryInst = null; }
	function onFilterChange() { markerStack = []; nextMarker = null; load(); }
	function onPrev() {
		const prev = markerStack.slice(0, -1);
		markerStack = prev;
		load(prev[prev.length - 1]);
	}
	function onNext() { if (!nextMarker) return; markerStack = [...markerStack, nextMarker]; load(nextMarker); }

	const ar = createAutoRefresh(
		() => { load(markerStack[markerStack.length - 1]); loadTimeseries(tsRange, { background: true }); },
		{ storageKey: 'admin-instances', defaultActive: true, defaultInterval: 15, intervalOptions: [10, 15, 30, 60] }
	);

	$effect(() => {
		const hasTransitional = allInstances.some(i => isTransitional(i.status));
		ar.setBoost(hasTransitional ? 4 : null);
	});

	async function bulkAction(action: 'start' | 'stop' | 'delete') {
		const ids = [...selectedIds];
		if (ids.length === 0) return;
		const labels: Record<string, string> = { start: '시작', stop: '종료', delete: '삭제' };
		if (action === 'stop' || action === 'delete') {
			const msg = action === 'delete'
				? `선택한 인스턴스 ${ids.length}개를 삭제하시겠습니까?`
				: `선택한 인스턴스 ${ids.length}개를 종료하시겠습니까?`;
			if (!await confirmDialog(msg)) return;
		}
		bulkActioning = true;
		try {
			const res = await api.post<{ results: { id: string; ok: boolean; error?: string }[] }>(
				'/api/instances/bulk-action',
				{ action, instance_ids: ids },
				token, projectId,
			);
			const failed = res.results.filter(r => !r.ok).length;
			const ok = res.results.filter(r => r.ok).length;
			if (ok > 0) toast.success(`${ok}개 ${labels[action]} 요청 완료`);
			if (failed > 0) toast.error(`${failed}개 처리 실패`);
			selectedIds = new Set();
			ar.setBoost(4);
			load(markerStack[markerStack.length - 1]);
		} catch {
			toast.error(`일괄 ${labels[action]} 요청 실패`);
		} finally {
			bulkActioning = false;
		}
	}

	onMount(() => {
		if (window.matchMedia('(max-width: 767px)').matches) pageSize = 10;
		load(); loadTimeseries(tsRange); loadHosts(); loadHealth(); projectNames.load(token, projectId);
	});
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
			<div class="flex items-center gap-1 text-xs text-gray-500 max-md:hidden">
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

	{#if health}
		<div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3.5 mb-4">
			<StatTile label="전체 VM" value={health.total} unit="instances" accent="blue" />
			<StatTile label="ACTIVE" value={health.active} unit="/ {health.total}" accent="emerald" />
			<StatTile label="ERROR" value={health.error} unit="instances" accent="rose" />
			<StatTile label="알림 있음" value={health.with_alerts} unit="instances" accent="amber" class="max-md:hidden" />
			<StatTile label="GPU VM" value={health.gpu_count} unit="가속" accent="violet" class="max-md:hidden" />
		</div>
	{/if}

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

	<!-- 일괄 액션 바 -->
	{#if selectedIds.size > 0}
		<div class="flex items-center gap-3 mb-3 px-4 py-2.5 bg-blue-950/60 border border-blue-800/60 rounded-xl">
			<span class="text-blue-300 text-sm font-medium">{selectedIds.size}개 선택됨</span>
			<div class="flex gap-2 ml-auto">
				<button type="button" disabled={bulkActioning} onclick={() => bulkAction('start')}
					class="px-3 py-1.5 text-xs font-medium rounded-lg bg-green-700/80 hover:bg-green-600/80 text-white disabled:opacity-50 transition-colors">시작</button>
				<button type="button" disabled={bulkActioning} onclick={() => bulkAction('stop')}
					class="px-3 py-1.5 text-xs font-medium rounded-lg bg-amber-700/80 hover:bg-amber-600/80 text-white disabled:opacity-50 transition-colors">종료</button>
				<button type="button" disabled={bulkActioning} onclick={() => bulkAction('delete')}
					class="px-3 py-1.5 text-xs font-medium rounded-lg bg-red-700/80 hover:bg-red-600/80 text-white disabled:opacity-50 transition-colors">삭제</button>
				<button type="button" onclick={() => { selectedIds = new Set(); }}
					class="px-3 py-1.5 text-xs font-medium rounded-lg bg-gray-700/80 hover:bg-gray-600/80 text-gray-300 transition-colors">취소</button>
			</div>
		</div>
	{/if}

	{#if loading}
		<LoadingSkeleton variant="table" rows={5} />
	{:else}
		<AdminInstanceTable
			instances={allInstances}
			{markerStack}
			{nextMarker}
			{refreshing}
			{selectedIds}
			onOpen={openDetail}
			{onPrev}
			{onNext}
			onRecover={openRecovery}
			onToggleSelect={(id) => {
				const next = new Set(selectedIds);
				if (next.has(id)) next.delete(id); else next.add(id);
				selectedIds = next;
			}}
			onToggleAll={() => {
				if (allInstances.every(i => selectedIds.has(i.id))) {
					selectedIds = new Set();
				} else {
					selectedIds = new Set(allInstances.map(i => i.id));
				}
			}}
		/>
	{/if}
</div>

{#if selectedInstanceId}
	<SlidePanel onClose={closeDetail}>
		<InstanceDetailPanel instanceId={selectedInstanceId} adminProjectId={selectedProjectId} onClose={closeDetail} />
	</SlidePanel>
{/if}

{#if recoveryInst}
	<RecoveryModal
		serverId={recoveryInst.id}
		serverName={recoveryInst.name || recoveryInst.id.slice(0, 8)}
		onClose={closeRecovery}
		onRecovered={() => { closeRecovery(); markerStack = []; nextMarker = null; load(); }}
	/>
{/if}
