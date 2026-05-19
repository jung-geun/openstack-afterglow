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
	}

	interface VolumeByType {
		type: string;
		count: number;
		total_gb: number;
	}

	interface UsageStats {
		range: string;
		top_instances: TopInstance[];
		volumes_by_type: VolumeByType[];
	}

	let data = $state<UsageStats | null>(null);
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
			const res = await api.get<UsageStats>(`/api/dashboard/usage-stats?range=${period}`, token, projectId);
			data = res;
		} catch (e) {
			error = e instanceof Error ? e.message : '데이터 로딩 실패';
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

	const VCPU_MAX = 32;
	const RAM_MAX = 32768;

	// Volume bar colors cycling through CSS tokens
	const VOL_COLORS = [
		'var(--color-accent)',
		'var(--color-accent-2)',
		'var(--color-warm)',
		'var(--color-state-info)',
		'var(--color-state-success)',
	];

	function volColor(i: number): string {
		return VOL_COLORS[i % VOL_COLORS.length];
	}

	function isGpu(flavorName: string): boolean {
		const lower = flavorName.toLowerCase();
		return lower.startsWith('g1.') || lower.startsWith('gpu');
	}

	const totalVolumeGb = $derived(
		data?.volumes_by_type.reduce((s, v) => s + v.total_gb, 0) ?? 0
	);
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
		<!-- Spark trend cards -->
		<div class="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
			{#each [
				{ key: 'vCPU', unit: 'cores' },
				{ key: 'RAM', unit: 'GB' },
				{ key: '네트워크', unit: 'Mbps' },
			] as card}
				<div class="bg-gray-900 border border-gray-800 rounded-2xl p-5">
					<SectionHeader title="{card.key} 24h 추세" meta={card.unit} />
					<div class="mt-4 flex items-center justify-center h-14 text-[11px] text-gray-500">
						Prometheus 미설정
					</div>
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
								<th class="text-left pb-2 text-[10px] uppercase tracking-wide text-[var(--color-ink-3)] font-medium w-32">vCPU</th>
								<th class="text-left pb-2 text-[10px] uppercase tracking-wide text-[var(--color-ink-3)] font-medium w-32">RAM</th>
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
											<span class="text-white w-4 text-right font-medium">{inst.vcpus}</span>
											<div class="flex-1 min-w-[60px]">
												<QuotaBar label="" used={inst.vcpus} limit={VCPU_MAX} size="xs" />
											</div>
										</div>
									</td>
									<td class="py-2.5 pr-4">
										<div class="flex items-center gap-2">
											<span class="text-white w-10 text-right font-medium">{Math.round(inst.ram_mb / 1024)}G</span>
											<div class="flex-1 min-w-[60px]">
												<QuotaBar label="" used={inst.ram_mb} limit={RAM_MAX} size="xs" />
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

		<!-- 2-col row: 14d trend + volume distribution -->
		<div class="grid grid-cols-1 lg:grid-cols-2 gap-3.5">
			<!-- 14d trend -->
			<div class="bg-gray-900 border border-gray-800 rounded-2xl p-5">
				<SectionHeader title="14일 추세" />
				<div class="mt-4 flex items-center justify-center h-20 text-[11px] text-gray-500">
					Prometheus 미설정
				</div>
			</div>

			<!-- Volume distribution -->
			<div class="bg-gray-900 border border-gray-800 rounded-2xl p-5">
				<SectionHeader title="볼륨 분포" meta="{data.volumes_by_type.length}종" />
				{#if data.volumes_by_type.length === 0}
					<div class="mt-4 text-sm text-gray-500 text-center py-4">볼륨 없음</div>
				{:else}
					<div class="mt-4 space-y-3">
						{#each data.volumes_by_type as vol, i}
							{@const pct = totalVolumeGb > 0 ? Math.round((vol.total_gb / totalVolumeGb) * 100) : 0}
							<div>
								<div class="flex justify-between text-xs mb-1.5">
									<span class="text-gray-400 uppercase tracking-wide">{vol.type}</span>
									<span class="text-gray-500">
										<span class="text-white font-medium">{vol.total_gb} GB</span>
										· {vol.count}개 · {pct}%
									</span>
								</div>
								<div class="h-1 bg-gray-800 rounded-full overflow-hidden">
									<div
										class="h-full rounded-full transition-all"
										style="width:{pct}%; background:{volColor(i)}"
									></div>
								</div>
							</div>
						{/each}
					</div>
				{/if}
			</div>
		</div>
	{:else}
		<div class="text-gray-500 text-sm py-8 text-center">데이터 없음</div>
	{/if}
</div>
