<script lang="ts">
	import { untrack } from 'svelte';
	import { auth, authReady } from '$lib/stores/auth';
	import { api } from '$lib/api/client';
	import type { DashboardSummary, Quotas, Instance } from '$lib/types/resources';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import DashboardGreetingHeader from '$lib/components/dashboard/overview/DashboardGreetingHeader.svelte';
	import DashboardStatTiles from '$lib/components/dashboard/overview/DashboardStatTiles.svelte';
	import RecentInstancesCard from '$lib/components/dashboard/overview/RecentInstancesCard.svelte';
	import QuotaUsageCard from '$lib/components/dashboard/overview/QuotaUsageCard.svelte';

	let summary = $state<DashboardSummary | null>(null);
	let summaryLoading = $state(true);
	let quotas = $state<Quotas | null>(null);
	let recentInstances = $state<Instance[]>([]);
	let k3sCount = $state<number | null>(null);
	let refreshing = $state(false);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	let inFlight: AbortController | null = null;

	async function fetchAll(opts?: { refresh?: boolean }) {
		inFlight?.abort();
		const ctrl = new AbortController();
		inFlight = ctrl;
		if (!summary) summaryLoading = true;
		try {
			await Promise.allSettled([
				api.get<DashboardSummary>('/api/dashboard/summary', token, projectId, { ...opts, signal: ctrl.signal })
					.then(v => { if (!ctrl.signal.aborted) { summary = v; summaryLoading = false; } })
					.catch(() => { summaryLoading = false; }),
				api.get<Quotas>('/api/dashboard/quotas', token, projectId, { signal: ctrl.signal })
					.then(v => { if (!ctrl.signal.aborted) quotas = v; })
					.catch(() => {}),
				api.get<Instance[]>('/api/instances', token, projectId, { ...opts, signal: ctrl.signal })
					.then(v => { if (!ctrl.signal.aborted) recentInstances = v.slice(0, 5); })
					.catch(() => {}),
				api.get<unknown[]>('/api/k3s/clusters', token, projectId, { signal: ctrl.signal })
					.then(v => { if (!ctrl.signal.aborted) k3sCount = v.filter((c: any) => c.status === 'ACTIVE' || c.provisioning_status === 'ACTIVE').length; })
					.catch(() => { k3sCount = null; }),
			]);
		} finally {
			if (inFlight === ctrl) inFlight = null;
			summaryLoading = false;
		}
	}

	async function forceRefresh() {
		refreshing = true;
		try { await fetchAll({ refresh: true }); }
		finally { refreshing = false; }
	}

	const ar = createAutoRefresh(() => fetchAll(), {
		storageKey: 'dashboard-home',
		defaultActive: true,
		defaultInterval: 30,
		intervalOptions: [10, 15, 30, 60],
		invokeOnMount: false,
	});

	$effect(() => {
		const pid = $auth.projectId;
		const ready = $authReady;
		if (!pid || !ready) return;
		untrack(() => fetchAll());
	});
</script>

<div class="p-6 max-w-7xl mx-auto flex flex-col gap-5">
	<DashboardGreetingHeader
		username={$auth.username ?? ''}
		projectName={$auth.projectName ?? '—'}
		{ar}
		{refreshing}
		onForceRefresh={forceRefresh}
	/>

	<DashboardStatTiles
		{summary}
		{quotas}
		{k3sCount}
		loading={summaryLoading}
	/>

	<div class="grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-3.5">
		<RecentInstancesCard instances={recentInstances} loading={summaryLoading} />
		<QuotaUsageCard {summary} {quotas} />
	</div>
</div>
