<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import SlidePanel from '$lib/components/SlidePanel.svelte';
	import TimeSeriesChart from '$lib/components/TimeSeriesChart.svelte';
	import { projectNames } from '$lib/stores/projectNames';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import { openWizard } from '$lib/stores/wizard';
	import AdminVolumeFilters from '$lib/components/admin/volumes/AdminVolumeFilters.svelte';
	import AdminVolumeTable from '$lib/components/admin/volumes/AdminVolumeTable.svelte';
	import AdminVolumeEditModal from '$lib/components/admin/volumes/AdminVolumeEditModal.svelte';
	import AdminVolumeDeleteModal from '$lib/components/admin/volumes/AdminVolumeDeleteModal.svelte';
	import AdminVolumeExtendModal from '$lib/components/admin/volumes/AdminVolumeExtendModal.svelte';
	import AdminVolumeResetStatusModal from '$lib/components/admin/volumes/AdminVolumeResetStatusModal.svelte';
	import AdminVolumeForceDeleteModal from '$lib/components/admin/volumes/AdminVolumeForceDeleteModal.svelte';
	import AdminVolumeTransferModal from '$lib/components/admin/volumes/AdminVolumeTransferModal.svelte';

	interface AdminVolume {
		id: string;
		name: string;
		status: string;
		size: number;
		project_id: string | null;
		created_at: string | null;
		bootable?: boolean;
	}
	interface PagedResponse<T> {
		items: T[];
		next_marker: string | null;
		count: number;
	}
	interface TsPoint { ts: number; total?: number; in_use?: number; available?: number; [key: string]: number | undefined; }

	let allVolumes = $state<AdminVolume[]>([]);
	let loading = $state(true);
	let refreshing = $state(false);
	let pageSize = $state(20);
	let markerStack = $state<string[]>([]);
	let nextMarker = $state<string | null>(null);
	let tsData = $state<TsPoint[]>([]);
	let tsRange = $state('7d');
	let tsLoading = $state(true);

	let copiedProjectId = $state<string | null>(null);
	let openActionMenu = $state<string | null>(null);
	let selectedVolumeId = $state<string | null>(null);

	// 필터
	let projectFilter = $state('');
	let projectSearchText = $state('');
	let statusFilter = $state('');
	let nameSearch = $state('');

	// 모달 트리거
	let editVolume = $state<AdminVolume | null>(null);
	let deleteVolume = $state<AdminVolume | null>(null);
	let extendVolume = $state<AdminVolume | null>(null);
	let resetVolume = $state<AdminVolume | null>(null);
	let forceDeleteVolume = $state<AdminVolume | null>(null);
	let transferVolume = $state<AdminVolume | null>(null);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	function copyProjectId(id: string) {
		navigator.clipboard.writeText(id).then(() => {
			copiedProjectId = id;
			setTimeout(() => { copiedProjectId = null; }, 1500);
		});
	}

	async function loadTimeseries(range: string) {
		tsLoading = true;
		try {
			tsData = await api.get<TsPoint[]>(`/api/admin/timeseries/volumes?range=${range}`, token, projectId);
		} catch {
			tsData = [];
		} finally {
			tsLoading = false;
		}
	}

	async function load(marker?: string) {
		if (allVolumes.length === 0) loading = true;
		else refreshing = true;
		try {
			let url = `/api/admin/all-volumes?limit=${pageSize}`;
			if (marker) url += `&marker=${marker}`;
			if (projectFilter) url += `&project_id=${encodeURIComponent(projectFilter)}`;
			if (statusFilter) url += `&status=${encodeURIComponent(statusFilter)}`;
			if (nameSearch) url += `&name=${encodeURIComponent(nameSearch)}`;
			const res = await api.get<PagedResponse<AdminVolume>>(url, token, projectId);
			allVolumes = res.items;
			nextMarker = res.next_marker;
		} catch {
			allVolumes = [];
		} finally {
			loading = false;
			refreshing = false;
		}
	}

	const ar = createAutoRefresh(
		() => { load(markerStack[markerStack.length - 1]); loadTimeseries(tsRange); },
		{ storageKey: 'admin-volumes', defaultActive: true, defaultInterval: 30, intervalOptions: [15, 30, 60] },
	);

	onMount(() => {
		load();
		loadTimeseries(tsRange);
		projectNames.load(token, projectId);
	});
</script>

<div class="p-4 md:p-8 max-w-7xl mx-auto">
	<PageHeader breadcrumb="STORAGE / VOLUMES" title="전체 볼륨">
		{#snippet actions()}
			<AutoRefreshControl
				bind:active={ar.active}
				bind:intervalSeconds={ar.intervalSeconds}
				intervalOptions={ar.intervalOptions}
				refreshing={loading || refreshing}
				onManualRefresh={() => {
					markerStack = []; nextMarker = null;
					projectFilter = ''; projectSearchText = '';
					statusFilter = ''; nameSearch = '';
					load();
				}}
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

	<div class="mb-6">
		{#if tsLoading}
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-5 h-48 flex items-center justify-center">
				<div class="text-gray-600 text-sm">차트 로딩 중...</div>
			</div>
		{:else}
			<TimeSeriesChart
				data={tsData}
				title="볼륨 수 추이"
				mainKey="total"
				extraKeys={['in_use', 'available']}
				currentRange={tsRange}
				onRangeChange={(r) => { tsRange = r; loadTimeseries(r); }}
			/>
		{/if}
	</div>

	<AdminVolumeFilters
		bind:projectFilter
		bind:projectSearchText
		bind:statusFilter
		bind:nameSearch
		onChange={() => { markerStack = []; nextMarker = null; load(); }}
	/>

	{#if loading}
		<LoadingSkeleton variant="table" rows={5} />
	{:else}
		<div class:opacity-60={refreshing} class:pointer-events-none={refreshing}>
			<AdminVolumeTable
				volumes={allVolumes}
				{selectedVolumeId}
				{openActionMenu}
				{copiedProjectId}
				onSelect={(id) => (selectedVolumeId = id)}
				onActionMenuOpen={(id) => (openActionMenu = id)}
				onActionMenuClose={() => (openActionMenu = null)}
				onCopyProjectId={copyProjectId}
				onEdit={(v) => (editVolume = v)}
				onExtend={(v) => (extendVolume = v)}
				onTransfer={(v) => (transferVolume = v)}
				onReset={(v) => (resetVolume = v)}
				onForceDelete={(v) => (forceDeleteVolume = v)}
				onDelete={(v) => (deleteVolume = v)}
				onBootFromVolume={(v) =>
					openWizard({
						targetProjectId: v.project_id ?? undefined,
						prefill: { bootSource: 'volume', bootVolumeId: v.id, bootVolumeName: v.name },
					})}
			/>
		</div>
		<div class="flex items-center justify-between mt-3">
			<button
				disabled={markerStack.length === 0}
				onclick={() => {
					const prev = markerStack.slice(0, -1);
					const marker = prev[prev.length - 1];
					markerStack = prev;
					load(marker);
				}}
				class="px-3 py-1.5 text-xs rounded bg-gray-800 hover:bg-gray-700 text-gray-300 disabled:opacity-30 disabled:cursor-not-allowed"
			>← 이전</button>
			<button
				disabled={!nextMarker}
				onclick={() => {
					if (!nextMarker) return;
					markerStack = [...markerStack, nextMarker];
					load(nextMarker);
				}}
				class="px-3 py-1.5 text-xs rounded bg-gray-800 hover:bg-gray-700 text-gray-300 disabled:opacity-30 disabled:cursor-not-allowed"
			>다음 →</button>
		</div>
	{/if}
</div>

<!-- 볼륨 상세 패널 -->
{#if selectedVolumeId}
	<SlidePanel onClose={() => { selectedVolumeId = null; }} width="w-full md:w-[50vw] max-w-2xl">
		{#await import('$lib/components/AdminVolumeDetailPanel.svelte') then { default: Panel }}
			<Panel volumeId={selectedVolumeId} onClose={() => { selectedVolumeId = null; }} onRefresh={() => load(markerStack[markerStack.length - 1])} token={token} projectId={projectId} />
		{:catch}
			<div class="p-6">
				<a href="/admin/volumes/{selectedVolumeId}" class="text-blue-400 hover:text-blue-300">상세 페이지에서 보기 →</a>
			</div>
		{/await}
	</SlidePanel>
{/if}

<AdminVolumeEditModal
	volume={editVolume}
	onClose={() => (editVolume = null)}
	onSuccess={() => load()}
/>
<AdminVolumeDeleteModal
	volume={deleteVolume}
	onClose={() => (deleteVolume = null)}
	onSuccess={() => load()}
/>
<AdminVolumeExtendModal
	volume={extendVolume}
	onClose={() => (extendVolume = null)}
	onSuccess={() => load()}
/>
<AdminVolumeResetStatusModal
	volume={resetVolume}
	onClose={() => (resetVolume = null)}
	onSuccess={() => load(markerStack[markerStack.length - 1])}
/>
<AdminVolumeForceDeleteModal
	volume={forceDeleteVolume}
	onClose={() => (forceDeleteVolume = null)}
	onSuccess={() => load(markerStack[markerStack.length - 1])}
/>
<AdminVolumeTransferModal
	volume={transferVolume}
	onClose={() => (transferVolume = null)}
	onSuccess={() => load(markerStack[markerStack.length - 1])}
/>
