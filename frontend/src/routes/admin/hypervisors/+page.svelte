<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import { formatNumber, formatStorage } from '$lib/utils/format';
	import { projectNames } from '$lib/stores/projectNames';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import GrafanaEmbed from '$lib/components/monitoring/GrafanaEmbed.svelte';
	import HypervisorTable from '$lib/components/admin/hypervisors/HypervisorTable.svelte';
	import type { HypervisorRow } from '$lib/components/admin/hypervisors/HypervisorTable.svelte';
	import HypervisorDetailPanel from '$lib/components/admin/hypervisors/HypervisorDetailPanel.svelte';
	import type { HypervisorDetail } from '$lib/components/admin/hypervisors/HypervisorDetailPanel.svelte';
	import HypervisorMigrateModal from '$lib/components/admin/hypervisors/HypervisorMigrateModal.svelte';

	let hypervisors = $state<HypervisorRow[]>([]);
	let loading = $state(true);
	let refreshing = $state(false);
	let sortColumn = $state('');
	let sortAsc = $state(true);

	let selectedDetail = $state<HypervisorDetail | null>(null);
	let detailLoading = $state(false);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function load() {
		if (hypervisors.length === 0) loading = true;
		else refreshing = true;
		try {
			hypervisors = await api.get<HypervisorRow[]>('/api/admin/hypervisors', token, projectId);
		} catch {
			hypervisors = [];
		} finally {
			loading = false;
			refreshing = false;
		}
	}

	async function loadDetail(hvId: string) {
		detailLoading = true;
		selectedDetail = null;
		try {
			selectedDetail = await api.get<HypervisorDetail>(`/api/admin/hypervisors/${hvId}`, token, projectId);
		} catch {
			selectedDetail = null;
		} finally {
			detailLoading = false;
		}
	}

	function toggleSort(col: string) {
		if (sortColumn === col) {
			sortAsc = !sortAsc;
		} else {
			sortColumn = col;
			sortAsc = true;
		}
	}

	let sortedHypervisors = $derived(
		hypervisors.toSorted((a, b) => {
			if (!sortColumn) return 0;
			let va: string | number;
			let vb: string | number;
			if (sortColumn === 'name') {
				va = a.name;
				vb = b.name;
			} else {
				va = (a as unknown as Record<string, number>)[sortColumn] ?? 0;
				vb = (b as unknown as Record<string, number>)[sortColumn] ?? 0;
			}
			const cmp = typeof va === 'string' ? va.localeCompare(vb as string) : (va as number) - (vb as number);
			return sortAsc ? cmp : -cmp;
		})
	);

	let showMigrateModal = $state(false);
	let migrateContext = $state({ serverId: '', serverName: '', type: 'live' as 'live' | 'cold' });

	function openMigrate(id: string, name: string, t: 'live' | 'cold') {
		migrateContext = { serverId: id, serverName: name, type: t };
		showMigrateModal = true;
	}

	const ar = createAutoRefresh(load, {
		storageKey: 'admin-hypervisors',
		defaultActive: true,
		defaultInterval: 30,
		intervalOptions: [15, 30, 60]
	});

	onMount(() => {
		load();
		projectNames.load(token, projectId);
	});
</script>

<div class="flex h-full">
<div class="flex-1 p-4 md:p-8 max-w-7xl mx-auto overflow-auto">
	<PageHeader breadcrumb="COMPUTE / HYPERVISORS" title="하이퍼바이저">
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
	{:else if hypervisors.length === 0}
		<div class="text-gray-600 text-sm">하이퍼바이저가 없습니다</div>
	{:else}
		<div class:opacity-60={refreshing} class:pointer-events-none={refreshing}>
			<HypervisorTable
				hypervisors={sortedHypervisors}
				selectedId={selectedDetail?.id ?? null}
				{sortColumn}
				{sortAsc}
				onSort={toggleSort}
				onSelect={loadDetail}
			/>
		</div>
	{/if}
</div>

{#if selectedDetail !== null || detailLoading}
	<HypervisorDetailPanel
		detail={selectedDetail}
		loading={detailLoading}
		projectNameMap={$projectNames}
		onClose={() => { selectedDetail = null; }}
		onMigrate={openMigrate}
	/>
{/if}
</div>

{#if !loading}
<div class="mt-8">
	<h2 class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">하이퍼바이저 메트릭 (Node Exporter)</h2>
	<GrafanaEmbed
		dashboardKey="node"
		height={400}
		vars={selectedDetail ? { instance: `${selectedDetail.host_ip}:9100` } : {}}
	/>
</div>
{/if}

{#if showMigrateModal}
	<HypervisorMigrateModal
		bind:open={showMigrateModal}
		serverId={migrateContext.serverId}
		serverName={migrateContext.serverName}
		type={migrateContext.type}
		onMigrated={() => selectedDetail && loadDetail(selectedDetail.id)}
	/>
{/if}
