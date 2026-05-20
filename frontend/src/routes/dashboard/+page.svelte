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
	import RangeToggle from '$lib/components/dashboard/overview/RangeToggle.svelte';

	interface Notification {
		type: string;
		severity: string;
		message: string;
		count: number;
	}

	interface TrendSeries {
		data: number[];
		points: number;
		available: boolean;
	}

	interface TrendData {
		vcpu: TrendSeries;
		memory: TrendSeries;
		storage: TrendSeries;
		network: TrendSeries & { unit: string };
		prometheus_available: boolean;
		range: '24h' | '7d' | '14d';
	}

	let summary = $state<DashboardSummary | null>(null);
	let summaryLoading = $state(true);
	let quotas = $state<Quotas | null>(null);
	let recentInstances = $state<Instance[]>([]);
	let k3sCount = $state<number | null>(null);
	let notifications = $state<Notification[]>([]);
	let trendData = $state<TrendData | null>(null);
	let refreshing = $state(false);

	const _VALID_RANGES = ['24h', '7d', '14d'] as const;
	const _savedRange = typeof localStorage !== 'undefined'
		? localStorage.getItem('dashboard-overview-range') as '24h' | '7d' | '14d' | null
		: null;
	let range = $state<'24h' | '7d' | '14d'>(
		_savedRange && (_VALID_RANGES as readonly string[]).includes(_savedRange) ? _savedRange : '14d'
	);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	let inFlight: AbortController | null = null;

	async function fetchTrend(opts?: { refresh?: boolean }) {
		const qs = opts?.refresh ? `?range=${range}&refresh=true` : `?range=${range}`;
		try {
			const v = await api.get<TrendData>(`/api/dashboard/metrics/trend${qs}`, token, projectId);
			trendData = v;
		} catch {
			// Prometheus 미설치 시 silent fail
		}
	}

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
				api.get<{ notifications: Notification[] }>('/api/dashboard/notifications', token, projectId, { signal: ctrl.signal })
					.then(v => { if (!ctrl.signal.aborted) notifications = v.notifications ?? []; })
					.catch(() => {}),
				fetchTrend(opts),
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

	function handleRangeChange(r: '24h' | '7d' | '14d') {
		range = r;
		localStorage.setItem('dashboard-overview-range', r);
		if (token && projectId) fetchTrend();
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

	<!-- 사용 추세 -->
	<div class="flex items-center justify-between mb-1">
		<p class="text-[10px] uppercase tracking-wide text-[var(--color-ink-3)]">사용 추세</p>
		<RangeToggle value={range} onchange={handleRangeChange} />
	</div>
	<div class="grid grid-cols-1 md:grid-cols-3 gap-3.5">
		{#each [
			{ label: `vCPU 사용률 (${range})`, color: 'var(--color-accent)',   key: 'vcpu'    as const, unit: '%' },
			{ label: `메모리 (${range})`,       color: 'var(--color-accent-2)', key: 'memory'  as const, unit: '%' },
			{ label: `디스크 사용률 (${range})`, color: 'var(--color-warm)',     key: 'storage' as const, unit: '%',
			  fallback: '인스턴스에 node_exporter 미설치 — 게스트 OS 내부 설치 필요' },
		] as card}
			{@const series  = trendData?.[card.key]}
			{@const hasData = (series?.data?.length ?? 0) > 0}
			{@const current = hasData ? series!.data.at(-1)! : null}
			{@const min     = hasData ? Math.min(...series!.data) : null}
			{@const max     = hasData ? Math.max(...series!.data) : null}
			<div class="bg-gray-900 border border-gray-800 rounded-2xl p-5 flex flex-col gap-2">
				<div class="flex items-baseline justify-between">
					<p class="text-[10px] uppercase tracking-wide text-[var(--color-ink-3)]">{card.label}</p>
					{#if current !== null}
						<span class="text-xl font-semibold tabular-nums text-[var(--color-ink-0)]">
							{current.toFixed(1)}<span class="text-[10px] text-[var(--color-ink-3)] ml-0.5">{card.unit}</span>
						</span>
					{/if}
				</div>
				<div class="min-h-[72px] flex items-center">
					{#if hasData}
						<Spark data={series!.data} color={card.color} height={72} class="w-full" />
					{:else if !trendData || !trendData.prometheus_available}
						<p class="text-[11px] italic text-[var(--color-ink-3)]">메트릭 수집 미설정 — <a href="/dashboard/observability" class="underline hover:text-[var(--color-ink-0)]">Grafana 보기</a></p>
					{:else if 'fallback' in card}
						<p class="text-[11px] italic text-[var(--color-ink-3)]">{card.fallback} — <a href="/dashboard/observability" class="underline hover:text-[var(--color-ink-0)]">Grafana 보기</a></p>
					{:else}
						<p class="text-[11px] text-[var(--color-ink-3)]">수집 대기 중</p>
					{/if}
				</div>
				{#if hasData}
					<p class="text-[10px] tabular-nums text-[var(--color-ink-3)]">
						min {min!.toFixed(1)}{card.unit} · max {max!.toFixed(1)}{card.unit}
					</p>
				{/if}
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
