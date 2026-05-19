<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { api } from '$lib/api/client';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import {
		StatTile,
		SectionHeader,
		Pill,
		CapacityBar,
	} from '$lib/components/ui';

	interface FlavorHour {
		flavor: string;
		instance_count: number;
		usage_hours: number;
	}

	interface UsageReport {
		range: string;
		start: string;
		end: string;
		stats: {
			instance_hours: number;
			vcpu_hours: number;
			active_instances: number;
			total_instances: number;
		};
		flavor_hours: FlavorHour[];
		forecast: {
			vcpu_pct: number;
		};
	}

	let data = $state<UsageReport | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let period = $state<'7d' | '30d' | '90d'>('30d');

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function fetchData() {
		if (!token || !projectId) return;
		loading = !data;
		error = null;
		try {
			const res = await api.get<UsageReport>(`/api/dashboard/usage-report?range=${period}`, token, projectId);
			data = res;
		} catch (e) {
			error = e instanceof Error ? e.message : '데이터 로딩 실패';
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		void [token, projectId, period];
		fetchData();
	});

	const ar = createAutoRefresh(fetchData, {
		storageKey: 'dashboard-usage-report',
		defaultActive: true,
		defaultInterval: 300,
		invokeOnMount: false,
	});

	const days = $derived(period === '7d' ? 7 : period === '30d' ? 30 : 90);

	const dailyAvg = $derived(
		data ? Math.round(data.stats.instance_hours / days) : 0
	);

	const sortedFlavors = $derived(
		data
			? [...data.flavor_hours].sort((a, b) => b.usage_hours - a.usage_hours)
			: []
	);

	function isGpu(flavorName: string): boolean {
		const lower = flavorName.toLowerCase();
		return lower.startsWith('g1.') || lower.startsWith('gpu');
	}
</script>

<div class="p-6 max-w-7xl mx-auto space-y-6">
	<!-- Header -->
	<div>
		<div class="text-[10px] uppercase tracking-wide text-[var(--color-ink-3)] mb-1">
			USAGE REPORT · 사용량 리포트
		</div>
		<div class="flex items-start justify-between gap-4 flex-wrap">
			<div>
				<h1 class="text-2xl font-bold text-white">기간 사용량 &amp; 쿼터 예측</h1>
				<p class="text-sm text-gray-400 mt-0.5">
					{#if data}
						{data.start} ~ {data.end} ·
					{/if}
					인스턴스 활성 시간(instance-hours)
				</p>
			</div>
			<div class="flex items-center gap-2">
				{#each (['7d', '30d', '90d'] as const) as p}
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
		<!-- KPI StatTiles -->
		<div class="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
			<StatTile
				label="누계 인스턴스-시간"
				value={data.stats.instance_hours.toFixed(1)}
				unit="h"
				accent="blue"
			>
				{#snippet icon()}
					<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
						<circle cx="12" cy="12" r="10"/>
						<polyline points="12 6 12 12 16 14"/>
					</svg>
				{/snippet}
			</StatTile>

			<StatTile
				label="일평균 인스턴스-시간"
				value={dailyAvg}
				unit="h/일"
				accent="cyan"
			>
				{#snippet icon()}
					<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
						<rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
						<line x1="16" y1="2" x2="16" y2="6"/>
						<line x1="8" y1="2" x2="8" y2="6"/>
						<line x1="3" y1="10" x2="21" y2="10"/>
					</svg>
				{/snippet}
			</StatTile>

			<StatTile
				label="활성 인스턴스"
				value={data.stats.active_instances}
				unit="/ {data.stats.total_instances}"
				accent="emerald"
			>
				{#snippet icon()}
					<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
						<rect x="2" y="3" width="20" height="14" rx="2"/>
						<line x1="8" y1="21" x2="16" y2="21"/>
						<line x1="12" y1="17" x2="12" y2="21"/>
					</svg>
				{/snippet}
			</StatTile>

			<StatTile
				label="vCPU 시간"
				value={data.stats.vcpu_hours.toFixed(1)}
				unit="h"
				accent="violet"
			>
				{#snippet icon()}
					<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
						<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
					</svg>
				{/snippet}
			</StatTile>
		</div>

		<!-- Optimization hint -->
		{#if data.forecast.vcpu_pct >= 80}
			<div class="bg-gray-900 border border-[var(--color-state-warning)] rounded-2xl p-4 flex items-start gap-3">
				<svg class="flex-shrink-0 mt-0.5" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--color-state-warning)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
					<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
					<line x1="12" y1="9" x2="12" y2="13"/>
					<line x1="12" y1="17" x2="12.01" y2="17"/>
				</svg>
				<p class="text-sm text-[var(--color-state-warning)]">
					<span class="font-semibold">최적화 제안:</span> vCPU 사용률이 높습니다. 사용량이 낮은 인스턴스를 확인하세요.
				</p>
			</div>
		{/if}

		<!-- 2-col layout -->
		<div class="grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-3.5">
			<!-- Flavor usage table -->
			<div class="bg-gray-900 border border-gray-800 rounded-2xl p-5">
				<SectionHeader title="플레이버별 사용 시간" meta="{sortedFlavors.length}종" />
				{#if sortedFlavors.length === 0}
					<div class="mt-6 text-center text-sm text-gray-500 py-6">데이터 없음</div>
				{:else}
					<div class="mt-4 overflow-x-auto">
						<table class="w-full text-xs">
							<thead>
								<tr class="border-b border-gray-800">
									<th class="text-left pb-2 text-[10px] uppercase tracking-wide text-[var(--color-ink-3)] font-medium">Flavor</th>
									<th class="text-right pb-2 text-[10px] uppercase tracking-wide text-[var(--color-ink-3)] font-medium">사용 시간(h)</th>
									<th class="text-right pb-2 text-[10px] uppercase tracking-wide text-[var(--color-ink-3)] font-medium">VM 수</th>
								</tr>
							</thead>
							<tbody>
								{#each sortedFlavors as f}
									<tr class="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
										<td class="py-2.5">
											<div class="flex items-center gap-2">
												<span class="text-white font-mono">{f.flavor}</span>
												{#if isGpu(f.flavor)}
													<Pill tone="accent">GPU</Pill>
												{/if}
											</div>
										</td>
										<td class="py-2.5 text-right text-white font-medium">{f.usage_hours.toFixed(1)}</td>
										<td class="py-2.5 text-right text-gray-400">{f.instance_count}</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				{/if}
			</div>

			<!-- Quota forecast -->
			<div class="bg-gray-900 border border-gray-800 rounded-2xl p-5 flex flex-col gap-4">
				<SectionHeader title="쿼터 예측" />
				<div class="space-y-3">
					<CapacityBar
						label="vCPU 사용률"
						used={data.forecast.vcpu_pct}
						total={100}
						unit="%"
						size="sm"
					/>
				</div>
				<p class="text-[11px] text-gray-500 mt-auto">선형 예측 (7일 추세 기반)</p>
			</div>
		</div>
	{:else}
		<div class="text-gray-500 text-sm py-8 text-center">데이터 없음</div>
	{/if}
</div>
