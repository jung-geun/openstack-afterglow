<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api } from '$lib/api/client';
	import type { TsPoint } from '$lib/types/common';
	import type { AdminFileStorage } from '$lib/types/fileStorage';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import { projectNames } from '$lib/stores/projectNames';
	import AdminFileStorageTimeseries from '$lib/components/admin/file-storage/AdminFileStorageTimeseries.svelte';
	import AdminFileStorageTable from '$lib/components/admin/file-storage/AdminFileStorageTable.svelte';
	import Pagination from '$lib/components/ui/Pagination.svelte';

	let fileStorages = $state<AdminFileStorage[]>([]);
	let loading = $state(true);
	let refreshing = $state(false);
	let tsData = $state<TsPoint[]>([]);
	let tsRange = $state('7d');
	let tsLoading = $state(true);
	let pageSize = $state(20);
	let currentPage = $state(0);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	const totalPages = $derived(Math.ceil(fileStorages.length / pageSize));
	const displayedStorages = $derived(
		fileStorages.slice(currentPage * pageSize, (currentPage + 1) * pageSize)
	);

	async function loadTimeseries(range: string) {
		tsLoading = true;
		try {
			tsData = await api.get<TsPoint[]>(`/api/admin/timeseries/file_storage?range=${range}`, token, projectId);
		} catch {
			tsData = [];
		} finally {
			tsLoading = false;
		}
	}

	async function load() {
		if (fileStorages.length === 0) loading = true;
		else refreshing = true;
		currentPage = 0;
		try {
			fileStorages = await api.get<AdminFileStorage[]>('/api/admin/all-file-storages', token, projectId);
		} catch {
			fileStorages = [];
		} finally {
			loading = false;
			refreshing = false;
		}
	}

	const ar = createAutoRefresh(
		() => { load(); loadTimeseries(tsRange); },
		{ storageKey: 'admin-file-storage', defaultInterval: 30, intervalOptions: [15, 30, 60] }
	);

	onMount(() => {
		load();
		loadTimeseries(tsRange);
		projectNames.load(token, projectId);
	});
</script>

<div class="p-4 md:p-8 max-w-7xl mx-auto">
	<PageHeader breadcrumb="STORAGE / FILE STORAGE" title="파일 스토리지">
		{#snippet actions()}
			<select
				bind:value={pageSize}
				onchange={() => { currentPage = 0; }}
				class="text-xs bg-gray-800 border border-gray-700 text-gray-300 rounded px-2 py-1.5"
			>
				{#each [10, 20, 30, 50] as s}
					<option value={s}>{s}개</option>
				{/each}
			</select>
			<AutoRefreshControl
				bind:active={ar.active}
				bind:intervalSeconds={ar.intervalSeconds}
				intervalOptions={ar.intervalOptions}
				refreshing={loading || refreshing}
				onManualRefresh={load}
			/>
		{/snippet}
	</PageHeader>

	<div class="mb-6">
		<AdminFileStorageTimeseries
			data={tsData}
			loading={tsLoading}
			range={tsRange}
			onRangeChange={(r) => { tsRange = r; loadTimeseries(r); }}
		/>
	</div>

	{#if loading}
		<LoadingSkeleton variant="table" rows={5} />
	{:else if fileStorages.length === 0}
		<div class="text-gray-600 text-sm">파일 스토리지가 없습니다</div>
	{:else}
		<div class:opacity-60={refreshing} class:pointer-events-none={refreshing}>
			<AdminFileStorageTable storages={displayedStorages} />
			{#if totalPages > 1}
				<Pagination
					page={currentPage + 1}
					{totalPages}
					total={fileStorages.length}
					{pageSize}
					hasPrev={currentPage > 0}
					hasNext={currentPage < totalPages - 1}
					onPrev={() => { currentPage--; }}
					onNext={() => { currentPage++; }}
				/>
			{/if}
		</div>
	{/if}
</div>
