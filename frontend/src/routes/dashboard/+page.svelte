<script lang="ts">
	import { untrack } from 'svelte';
	import { auth, authReady } from '$lib/stores/auth';
	import { api } from '$lib/api/client';
	import type { DashboardSummary, Instance } from '$lib/types/compute';
	import type { DashboardQuotas as Quotas } from '$lib/types/quotas';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import { Spark, SectionHeader } from '$lib/components/ui';
	import DashboardGreetingHeader from '$lib/components/dashboard/overview/DashboardGreetingHeader.svelte';
	import DashboardStatTiles from '$lib/components/dashboard/overview/DashboardStatTiles.svelte';
	import RecentInstancesCard from '$lib/components/dashboard/overview/RecentInstancesCard.svelte';
	import QuotaUsageCard from '$lib/components/dashboard/overview/QuotaUsageCard.svelte';

	interface Notification {
		type: string;
		severity: string;
		message: string;
		count: number;
	}

	let summary = $state<DashboardSummary | null>(null);
	let summaryLoading = $state(true);
	let quotas = $state<Quotas | null>(null);
	let recentInstances = $state<Instance[]>([]);
	let k3sCount = $state<number | null>(null);
	let notifications = $state<Notification[]>([]);
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
				api.get<{ notifications: Notification[] }>('/api/admin/notifications', token, projectId, { signal: ctrl.signal })
					.then(v => { if (!ctrl.signal.aborted) notifications = v.notifications ?? []; })
					.catch(() => {}),
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

	function severityDotColor(severity: string): string {
		if (severity === 'danger' || severity === 'critical' || severity === 'error') {
			return 'var(--color-state-danger)';
		} else if (severity === 'warning') {
			return 'var(--color-state-warning)';
		} else if (severity === 'info') {
			return 'var(--color-state-info)';
		}
		return 'var(--color-ink-3)';
	}
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

	<!-- 14d 사용 추세 -->
	<div class="grid grid-cols-1 md:grid-cols-3 gap-3.5">
		{#each [
			{ label: 'vCPU 사용률 (14d)', color: 'var(--color-accent)' },
			{ label: '메모리 (14d)', color: 'var(--color-accent-2)' },
			{ label: '스토리지 (14d)', color: 'var(--color-warm)' },
		] as trend}
			<div class="bg-gray-900 border border-gray-800 rounded-2xl p-5">
				<p class="text-[10px] uppercase tracking-wide text-[var(--color-ink-3)] mb-3">{trend.label}</p>
				<Spark data={[]} color={trend.color} height={44} />
				<p class="text-[11px] italic text-[var(--color-ink-3)] mt-2">지표 수집 서버 미설정</p>
			</div>
		{/each}
	</div>

	<!-- Main 2-col layout -->
	<div class="grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-3.5">
		<RecentInstancesCard instances={recentInstances} loading={summaryLoading} />

		<!-- Right column: alerts + quota stacked -->
		<div class="flex flex-col gap-3.5">
			<!-- System Alerts card -->
			<div class="bg-gray-900 border border-gray-800 rounded-2xl p-5">
				<SectionHeader title="시스템 알림" />
				{#if notifications.length === 0}
					<p class="text-sm text-[var(--color-ink-3)] mt-4">알림 없음</p>
				{:else}
					<ul class="mt-3 flex flex-col gap-2">
						{#each notifications as notif}
							<li class="flex items-start gap-2.5 text-sm">
								<span
									class="mt-1.5 w-2 h-2 rounded-full flex-shrink-0"
									style="background: {severityDotColor(notif.severity)};"
								></span>
								<span class="flex-1 text-[var(--color-ink-0)] text-xs leading-snug">{notif.message}</span>
								{#if notif.count > 1}
									<span class="text-[10px] text-[var(--color-ink-3)] tabular-nums flex-shrink-0">×{notif.count}</span>
								{/if}
							</li>
						{/each}
					</ul>
				{/if}
			</div>

			<QuotaUsageCard {summary} {quotas} />
		</div>
	</div>
</div>
