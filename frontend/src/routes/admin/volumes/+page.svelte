<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api } from '$lib/api/client';
	import type { PagedResponse, TsPoint } from '$lib/types/common';
	import type { AdminVolume } from '$lib/types/volume';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
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
	import AdminVolumeTimeseries from '$lib/components/admin/volumes/AdminVolumeTimeseries.svelte';
	import AdminVolumePagination from '$lib/components/admin/volumes/AdminVolumePagination.svelte';
	import AdminVolumePageSizeToggle from '$lib/components/admin/volumes/AdminVolumePageSizeToggle.svelte';
	import AdminVolumeDetailSlide from '$lib/components/admin/volumes/AdminVolumeDetailSlide.svelte';

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

	let projectFilter = $state('');
	let projectSearchText = $state('');
	let statusFilter = $state('');
	let nameSearch = $state('');

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
			<AdminVolumePageSizeToggle
				value={pageSize}
				onChange={(n) => { pageSize = n; markerStack = []; nextMarker = null; load(); }}
			/>
		{/snippet}
	</PageHeader>

	<AdminVolumeTimeseries
		data={tsData}
		loading={tsLoading}
		range={tsRange}
		onRangeChange={(r) => { tsRange = r; loadTimeseries(r); }}
	/>

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
		<AdminVolumePagination
			{markerStack}
			{nextMarker}
			onPrev={() => {
				const prev = markerStack.slice(0, -1);
				const marker = prev[prev.length - 1];
				markerStack = prev;
				load(marker);
			}}
			onNext={() => {
				if (!nextMarker) return;
				markerStack = [...markerStack, nextMarker];
				load(nextMarker);
			}}
		/>
	{/if}
</div>

{#if selectedVolumeId}
	<AdminVolumeDetailSlide
		volumeId={selectedVolumeId}
		{token}
		{projectId}
		onClose={() => { selectedVolumeId = null; }}
		onRefresh={() => load(markerStack[markerStack.length - 1])}
	/>
{/if}

<AdminVolumeEditModal volume={editVolume} onClose={() => (editVolume = null)} onSuccess={() => load()} />
<AdminVolumeDeleteModal volume={deleteVolume} onClose={() => (deleteVolume = null)} onSuccess={() => load()} />
<AdminVolumeExtendModal volume={extendVolume} onClose={() => (extendVolume = null)} onSuccess={() => load()} />
<AdminVolumeResetStatusModal volume={resetVolume} onClose={() => (resetVolume = null)} onSuccess={() => load(markerStack[markerStack.length - 1])} />
<AdminVolumeForceDeleteModal volume={forceDeleteVolume} onClose={() => (forceDeleteVolume = null)} onSuccess={() => load(markerStack[markerStack.length - 1])} />
<AdminVolumeTransferModal volume={transferVolume} onClose={() => (transferVolume = null)} onSuccess={() => load(markerStack[markerStack.length - 1])} />
