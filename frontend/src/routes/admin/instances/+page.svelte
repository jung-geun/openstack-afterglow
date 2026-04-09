<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import TimeSeriesChart from '$lib/components/TimeSeriesChart.svelte';
	import InstanceDetailPanel from '$lib/components/InstanceDetailPanel.svelte';
	import { formatNumber } from '$lib/utils/format';
	import { projectNames } from '$lib/stores/projectNames';

	interface AdminInstance {
		id: string;
		name: string;
		status: string;
		project_id: string | null;
		user_id: string | null;
		flavor: string;
		host: string | null;
		created_at: string | null;
		fault?: string | null;
	}
	interface PagedResponse<T> {
		items: T[];
		next_marker: string | null;
		count: number;
	}
	interface TsPoint {
		ts: number;
		total?: number;
		active?: number;
		shutoff?: number;
		error?: number;
		shelved?: number;
		[key: string]: number | undefined;
	}

	const statusColor: Record<string, string> = {
		ACTIVE:            'text-green-400',
		SHUTOFF:           'text-gray-400',
		ERROR:             'text-red-400',
		BUILD:             'text-yellow-400',
		SHELVED_OFFLOADED: 'text-purple-400',
		SHELVED:           'text-purple-400',
	};

	let allInstances = $state<AdminInstance[]>([]);
	let loading = $state(true);
	let pageSize = $state(20);
	let markerStack = $state<string[]>([]);
	let nextMarker = $state<string | null>(null);
	let expandedError = $state<string | null>(null);
	let copiedProjectId = $state<string | null>(null);

	function copyProjectId(id: string) {
		navigator.clipboard.writeText(id).then(() => {
			copiedProjectId = id;
			setTimeout(() => { copiedProjectId = null; }, 1500);
		});
	}

	// 필터
	let hostFilter = $state('');
	let projectFilter = $state('');
	let uniqueHosts = $derived([...new Set(allInstances.map(i => i.host).filter(Boolean) as string[])].sort());
	let filteredInstances = $derived(
		allInstances.filter(i =>
			(!hostFilter || i.host === hostFilter) &&
			(!projectFilter || (i.project_id ?? '').toLowerCase().includes(projectFilter.toLowerCase()))
		)
	);

	// 시계열 차트
	let tsData = $state<TsPoint[]>([]);
	let tsRange = $state('7d');
	let tsLoading = $state(true);

	// 인스턴스 상세 패널
	let selectedInstanceId = $state<string | null>(null);
	let selectedProjectId = $state<string | null>(null);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function load(marker?: string) {
		loading = true;
		try {
			let url = `/api/admin/all-instances?limit=${pageSize}`;
			if (marker) url += `&marker=${marker}`;
			const res = await api.get<PagedResponse<AdminInstance>>(url, token, projectId);
			allInstances = res.items;
			nextMarker = res.next_marker;
		} catch {
			allInstances = [];
		} finally {
			loading = false;
		}
	}

	async function loadTimeseries(range: string) {
		tsLoading = true;
		try {
			tsData = await api.get<TsPoint[]>(`/api/admin/timeseries/instances?range=${range}`, token, projectId);
		} catch {
			tsData = [];
		} finally {
			tsLoading = false;
		}
	}

	function openDetail(inst: AdminInstance) {
		selectedInstanceId = inst.id;
		selectedProjectId = inst.project_id;
	}

	function closeDetail() {
		selectedInstanceId = null;
		selectedProjectId = null;
	}

	onMount(() => {
		load();
		loadTimeseries(tsRange);
		projectNames.load(token, projectId);
	});
</script>

<div class="p-4 md:p-8 max-w-6xl">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-white">전체 인스턴스</h1>
		<div class="flex items-center gap-3">
			<button onclick={() => { markerStack = []; nextMarker = null; hostFilter = ''; projectFilter = ''; load(); }} class="text-xs text-gray-400 hover:text-white transition-colors px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600">새로고침</button>
			<div class="flex items-center gap-1 text-xs text-gray-500">
				표시:
				{#each [10, 20, 30] as n}
					<button
						onclick={() => { pageSize = n; markerStack = []; nextMarker = null; load(); }}
						class="px-2 py-0.5 rounded {pageSize === n ? 'bg-blue-600 text-white' : 'bg-gray-800 hover:bg-gray-700 text-gray-400'}"
					>{n}</button>
				{/each}
			</div>
		</div>
	</div>

	<!-- 필터 -->
	<div class="flex gap-3 mb-4">
		<select bind:value={hostFilter} class="bg-gray-800 border border-gray-700 text-sm text-gray-300 rounded-lg px-2 py-1.5 focus:outline-none focus:border-blue-500">
			<option value="">모든 호스트</option>
			{#each uniqueHosts as h}
				<option value={h}>{h}</option>
			{/each}
		</select>
		<input
			type="text"
			placeholder="프로젝트 ID 필터"
			bind:value={projectFilter}
			class="bg-gray-800 border border-gray-700 text-sm text-gray-300 rounded-lg px-3 py-1.5 w-52 focus:outline-none focus:border-blue-500"
		/>
	</div>

	<!-- 시계열 차트 -->
	<div class="mb-6">
		{#if tsLoading}
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-5 h-48 flex items-center justify-center">
				<div class="text-gray-600 text-sm">차트 로딩 중...</div>
			</div>
		{:else}
			<TimeSeriesChart
				data={tsData}
				title="인스턴스 수 추이"
				mainKey="total"
				extraKeys={['active', 'shutoff', 'error', 'shelved']}
				currentRange={tsRange}
				onRangeChange={(r) => { tsRange = r; loadTimeseries(r); }}
			/>
		{/if}
	</div>

	{#if loading}
		<LoadingSkeleton variant="table" rows={5} />
	{:else}
		<div class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
						<th class="text-left py-2 pr-4">이름</th>
						<th class="text-left py-2 pr-4">상태</th>
						<th class="text-left py-2 pr-4">Flavor</th>
						<th class="text-left py-2 pr-4">호스트</th>
						<th class="text-left py-2 pr-4">프로젝트</th>
						<th class="text-left py-2">생성일</th>
					</tr>
				</thead>
				<tbody>
					{#each filteredInstances as s (s.id)}
						<tr
							onclick={() => openDetail(s)}
							class="border-b border-gray-800/50 text-xs hover:bg-gray-800/50 transition-colors cursor-pointer"
						>
							<td class="py-2 pr-4 text-white">{s.name || s.id.slice(0, 8)}</td>
							<td class="py-2 pr-4">
								<div class="flex items-center gap-1.5">
									<span class="{statusColor[s.status] ?? 'text-gray-400'}">{s.status}</span>
									{#if s.status === 'ERROR' && s.fault}
										<button
											onclick={(e) => { e.stopPropagation(); expandedError = expandedError === s.id ? null : s.id; }}
											class="text-red-500 hover:text-red-300 text-xs underline"
											title={s.fault}
										>사유</button>
									{/if}
								</div>
								{#if expandedError === s.id && s.fault}
									<div class="mt-1 text-red-400 bg-red-900/20 border border-red-900/50 rounded px-2 py-1 text-xs max-w-xs break-words">
										{s.fault}
									</div>
								{/if}
							</td>
							<td class="py-2 pr-4 text-gray-400">{s.flavor || '-'}</td>
							<td class="py-2 pr-4 text-gray-400">{s.host || '-'}</td>
							<td class="py-2 pr-4">
								<button
									onclick={(e) => { e.stopPropagation(); if (s.project_id) copyProjectId(s.project_id); }}
									class="text-gray-400 hover:text-blue-400 transition-colors cursor-pointer text-left"
									title={s.project_id ?? ''}
								>
									{#if copiedProjectId === s.project_id}
										<span class="text-green-400 text-xs">복사됨</span>
									{:else}
										<span class="text-xs">{s.project_id ? ($projectNames.get(s.project_id) ?? s.project_id.slice(0, 8)) : '-'}</span>
									{/if}
								</button>
							</td>
							<td class="py-2 text-gray-500">{s.created_at?.slice(0, 10) ?? '-'}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		<div class="flex items-center justify-between mt-3">
			<button
				disabled={markerStack.length === 0}
				onclick={() => {
					const prev = markerStack.slice(0, -1);
					const marker = prev[prev.length - 1];
					markerStack = prev;
					load(marker);
				}}
				class="px-3 py-1.5 text-xs rounded bg-gray-800 hover:bg-gray-700 text-gray-300 disabled:opacity-30 disabled:cursor-not-allowed"
			>← 이전</button>
			<button
				disabled={!nextMarker}
				onclick={() => {
					if (!nextMarker) return;
					markerStack = [...markerStack, nextMarker];
					load(nextMarker);
				}}
				class="px-3 py-1.5 text-xs rounded bg-gray-800 hover:bg-gray-700 text-gray-300 disabled:opacity-30 disabled:cursor-not-allowed"
			>다음 →</button>
		</div>
	{/if}
</div>

{#if selectedInstanceId}
	<div class="fixed inset-0 z-40" role="dialog" aria-modal="true" onkeydown={(e) => e.key === 'Escape' && closeDetail()} tabindex="-1">
		<button class="absolute inset-0 bg-black/50 cursor-default" onclick={closeDetail} aria-label="패널 닫기"></button>
		<div class="absolute right-0 top-14 bottom-0 w-full md:w-[75vw] max-w-5xl bg-gray-950 border-l border-gray-700 overflow-y-auto shadow-2xl">
			<InstanceDetailPanel instanceId={selectedInstanceId} adminProjectId={selectedProjectId} onClose={closeDetail} />
		</div>
	</div>
{/if}