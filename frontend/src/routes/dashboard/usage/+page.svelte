<script lang="ts">
	import { untrack } from 'svelte';
	import { auth, authReady } from '$lib/stores/auth';
	import { api } from '$lib/api/client';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import {
		SectionHeader,
		Pill,
		QuotaBar,
		StatusChip,
		Spark,
	} from '$lib/components/ui';

	interface TopInstance {
		id: string;
		name: string;
		flavor_name: string;
		vcpus: number;
		ram_mb: number;
		disk_gb: number;
		status: string;
		usage_hours: number;
		cpu_pct?: number | null;
		ram_pct?: number | null;
	}

	interface UsageStats {
		range: string;
		top_instances: TopInstance[];
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

	let data = $state<UsageStats | null>(null);
	let trendData = $state<TrendData | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let period = $state<'24h' | '7d' | '30d'>('7d');

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function fetchData() {
		if (!token || !projectId) return;
		loading = !data;
		error = null;
		try {
			await Promise.allSettled([
				api.get<UsageStats>(`/api/dashboard/usage-stats?range=${period}`, token, projectId)
					.then(v => { data = v; })
					.catch(e => { error = e instanceof Error ? e.message : '데이터 로딩 실패'; }),
				api.get<TrendData>('/api/dashboard/metrics/trend?range=24h', token, projectId)
					.then(v => { trendData = v; })
					.catch(() => {}),
			]);
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		const pid = $auth.projectId;
		const ready = $authReady;
		void [token, projectId, period];
		if (!pid || !ready) return;
		untrack(() => fetchData());
	});

	const ar = createAutoRefresh(fetchData, {
		storageKey: 'dashboard-usage',
		defaultActive: true,
		defaultInterval: 60,
		invokeOnMount: false,
	});

	function isGpu(flavorName: string): boolean {
		const lower = flavorName.toLowerCase();
		return lower.startsWith('g1.') || lower.startsWith('gpu');
	}

	function scaleNetwork(data: number[]): { data: number[]; unit: string } {
		const maxVal = data.length > 0 ? Math.max(...data) : 0;
		if (maxVal >= 1024 * 1024) return { data: data.map(v => v / (1024 * 1024)), unit: 'GiB/s' };
		if (maxVal >= 1024) return { data: data.map(v => v / 1024), unit: 'MiB/s' };
		return { data, unit: 'KiB/s' };
	}
</script>

<div class="p-6 max-w-7xl mx-auto space-y-6">
	<!-- Header -->
	<div>
		<div class="text-[10px] uppercase tracking-wide text-[var(--color-ink-3)] mb-1">
			USAGE · 내 프로젝트
		</div>
		<div class="flex items-start justify-between gap-4 flex-wrap">
			<div>
				<h1 class="text-2xl font-bold text-white">사용량</h1>
				<p class="text-sm text-gray-400 mt-0.5">{$auth.projectName ?? '—'}</p>
			</div>
			<div class="flex items-center gap-2">
				{#each (['24h', '7d', '30d'] as const) as p}
					<button
						onclick={() => { period = p; }}
						class="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors {period === p ? 'bg-[var(--color-accent)] text-white' : 'bg-gray-800 text-gray-400 hover:text-white'}"
					>{p}</button>
				{/each}
				<button
					onclick={() => { ar.active = !ar.active; }}
					class="px-3 py-1.5 rounded-lg text-xs transition-colors {ar.active ? 'bg-gray-700 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'}"
					title="자동 새로고침"
				>↻</button>
			</div>
		</div>
	</div>

	{#if loading}
		<div class="text-gray-400 text-sm py-8 text-center">로딩 중...</div>
	{:else if error}
		<div class="text-[var(--color-state-danger)] text-sm py-4">{error}</div>
	{:else if data}
		<!-- Spark trend cards — 24h 추세 (3-row: 현재값 + 그래프 + min/max) -->
		<div class="grid grid-cols-1 sm:grid-cols-4 gap-3.5">
			{#each [
				{ label: 'vCPU 24h 추세',    unit: '%',     color: 'var(--color-accent)',      key: 'vcpu'    as const },
				{ label: 'RAM 24h 추세',      unit: '%',     color: 'var(--color-accent-2)',    key: 'memory'  as const },
				{ label: '디스크 24h 추세',   unit: '%',     color: 'var(--color-warm)',        key: 'storage' as const,
				  fallback: '인스턴스에 node_exporter 미설치 — 게스트 OS 내부 설치 필요' },
				{ label: '네트워크 24h 추세', unit: trendData?.network?.unit ?? 'KiB/s', color: 'var(--color-state-info)', key: 'network' as const },
			] as card}
				{@const rawSeries  = trendData?.[card.key]}
				{@const netScaled  = card.key === 'network' && rawSeries?.data?.length ? scaleNetwork(rawSeries.data) : null}
				{@const seriesData = netScaled ? netScaled.data : (rawSeries?.data ?? [])}
				{@const displayUnit = netScaled ? netScaled.unit : card.unit}
				{@const hasData = seriesData.length > 0}
				{@const current = hasData ? seriesData.at(-1)! : null}
				{@const min     = hasData ? Math.min(...seriesData) : null}
				{@const max     = hasData ? Math.max(...seriesData) : null}
				<div class="bg-gray-900 border border-gray-800 rounded-2xl p-5 flex flex-col gap-2">
					<div class="flex items-baseline justify-between">
						<p class="text-[10px] uppercase tracking-wide text-[var(--color-ink-3)]">{card.label}</p>
						{#if current !== null}
							<span class="text-xl font-semibold tabular-nums text-[var(--color-ink-0)]">
								{current.toFixed(1)}<span class="text-[10px] text-[var(--color-ink-3)] ml-0.5">{displayUnit}</span>
							</span>
						{/if}
					</div>
					<div class="min-h-[72px] flex items-center">
						{#if hasData}
							<Spark data={seriesData} color={card.color} height={72} class="w-full" />
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
							min {min!.toFixed(1)}{displayUnit} · max {max!.toFixed(1)}{displayUnit}
						</p>
					{/if}
				</div>
			{/each}
		</div>

		<!-- Top consumers table -->
		<div class="bg-gray-900 border border-gray-800 rounded-2xl p-5">
			<SectionHeader title="상위 인스턴스" meta="{data.top_instances.length}개" />
			{#if data.top_instances.length === 0}
				<div class="mt-6 text-center text-sm text-gray-500 py-6">인스턴스 없음</div>
			{:else}
				<div class="mt-4 overflow-x-auto">
					<table class="w-full text-xs">
						<thead>
							<tr class="border-b border-gray-800">
								<th class="text-left pb-2 text-[10px] uppercase tracking-wide text-[var(--color-ink-3)] font-medium w-8">#</th>
								<th class="text-left pb-2 text-[10px] uppercase tracking-wide text-[var(--color-ink-3)] font-medium">인스턴스</th>
								<th class="text-left pb-2 text-[10px] uppercase tracking-wide text-[var(--color-ink-3)] font-medium">플레이버</th>
								<th class="text-left pb-2 text-[10px] uppercase tracking-wide text-[var(--color-ink-3)] font-medium w-44">vCPU</th>
								<th class="text-left pb-2 text-[10px] uppercase tracking-wide text-[var(--color-ink-3)] font-medium w-44">RAM</th>
								<th class="text-left pb-2 text-[10px] uppercase tracking-wide text-[var(--color-ink-3)] font-medium">상태</th>
							</tr>
						</thead>
						<tbody>
							{#each data.top_instances as inst, i}
								<tr class="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
									<td class="py-2.5 text-gray-500 font-mono">{i + 1}</td>
									<td class="py-2.5">
										<div class="flex items-center gap-2">
											<span class="text-white font-medium truncate max-w-[140px]">{inst.name}</span>
											{#if isGpu(inst.flavor_name)}
												<Pill tone="accent">GPU</Pill>
											{/if}
										</div>
									</td>
									<td class="py-2.5 text-gray-400 font-mono">{inst.flavor_name}</td>
									<td class="py-2.5 pr-4">
										<div class="flex items-center gap-2">
											<span class="tabular-nums text-white font-medium whitespace-nowrap">{inst.vcpus} vCPU</span>
											<span class="tabular-nums text-[var(--color-ink-3)] w-8 text-right shrink-0">
												{inst.cpu_pct != null ? `${inst.cpu_pct.toFixed(0)}%` : '—'}
											</span>
											<div class="flex-1 min-w-[48px]">
												<QuotaBar label="" used={inst.cpu_pct ?? 0} limit={100} size="xs" showValue={false} />
											</div>
										</div>
									</td>
									<td class="py-2.5 pr-4">
										<div class="flex items-center gap-2">
											<span class="tabular-nums text-white font-medium whitespace-nowrap">{Math.round(inst.ram_mb / 1024)} GB</span>
											<span class="tabular-nums text-[var(--color-ink-3)] w-8 text-right shrink-0">
												{inst.ram_pct != null ? `${inst.ram_pct.toFixed(0)}%` : '—'}
											</span>
											<div class="flex-1 min-w-[48px]">
												<QuotaBar label="" used={inst.ram_pct ?? 0} limit={100} size="xs" showValue={false} />
											</div>
										</div>
									</td>
									<td class="py-2.5">
										<StatusChip status={inst.status} />
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</div>
	{:else}
		<div class="text-gray-500 text-sm py-8 text-center">데이터 없음</div>
	{/if}
</div>
