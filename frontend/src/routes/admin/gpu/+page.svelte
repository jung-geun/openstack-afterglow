<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import type { AggregatedHost, GpuType, GpuResponse } from '$lib/types/gpu';
	import GpuSummaryCards from '$lib/components/admin/gpu/GpuSummaryCards.svelte';
	import GpuTypeFilterGrid from '$lib/components/admin/gpu/GpuTypeFilterGrid.svelte';
	import GpuHostFilterBar from '$lib/components/admin/gpu/GpuHostFilterBar.svelte';
	import GpuHostTable from '$lib/components/admin/gpu/GpuHostTable.svelte';

	let aggregatedHosts = $state<AggregatedHost[]>([]);
	let summary = $state({ total_hosts: 0, total_gpus: 0, used_gpus: 0, available_gpus: 0 });
	let gpuTypes = $state<GpuType[]>([]);
	let loading = $state(true);
	let refreshing = $state(false);
	let error = $state('');
	let availableFilter = $state<'all' | 'available' | 'full'>('all');
	let selectedGpuTypes = $state<Set<string>>(new Set());

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function load() {
		if (aggregatedHosts.length === 0) loading = true;
		else refreshing = true;
		error = '';
		try {
			const res = await api.get<GpuResponse>('/api/admin/gpu-hosts', token, projectId);
			aggregatedHosts = res.aggregated_hosts ?? [];
			summary = res.summary;
			gpuTypes = res.gpu_types ?? [];
		} catch (e) {
			error = e instanceof ApiError ? e.message : 'GPU 정보를 불러올 수 없습니다';
			aggregatedHosts = [];
		} finally {
			loading = false;
			refreshing = false;
		}
	}

	function toggleGpuType(deviceName: string) {
		const next = new Set(selectedGpuTypes);
		if (next.has(deviceName)) next.delete(deviceName);
		else next.add(deviceName);
		selectedGpuTypes = next;
	}

	let filteredHosts = $derived(
		aggregatedHosts.filter((h) => {
			if (availableFilter === 'available' && h.gpu_total - h.gpu_used <= 0) return false;
			if (availableFilter === 'full' && h.gpu_total - h.gpu_used !== 0) return false;
			if (selectedGpuTypes.size > 0 && !h.gpu_groups.some((g) => selectedGpuTypes.has(g.device_name))) return false;
			return true;
		})
	);

	const ar = createAutoRefresh(load, {
		storageKey: 'admin-gpu',
		defaultActive: true,
		defaultInterval: 30,
		intervalOptions: [15, 30, 60]
	});

	onMount(load);
</script>

<div class="p-4 md:p-8 max-w-7xl mx-auto">
	<PageHeader breadcrumb="COMPUTE / GPU" title="GPU">
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

	{#if error}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>
	{/if}

	{#if loading}
		<LoadingSkeleton variant="table" rows={5} />
	{:else}
		<div class:opacity-60={refreshing} class:pointer-events-none={refreshing}>
			<GpuSummaryCards {summary} />

			<GpuTypeFilterGrid {gpuTypes} bind:selectedGpuTypes onToggle={toggleGpuType} />

			<GpuHostFilterBar bind:availableFilter bind:selectedGpuTypes />

			<GpuHostTable hosts={filteredHosts} />

			{#if aggregatedHosts.length === 0}
				<div class="text-center text-gray-500 text-sm py-8">GPU가 있는 호스트가 없습니다</div>
			{:else if filteredHosts.length === 0}
				<div class="text-center text-gray-500 text-sm py-8">조건에 맞는 호스트가 없습니다</div>
			{/if}
		</div>
	{/if}
</div>
