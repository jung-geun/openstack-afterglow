<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import TimeSeriesChart from '$lib/components/TimeSeriesChart.svelte';
	import InstanceDetailPanel from '$lib/components/InstanceDetailPanel.svelte';
	import SlidePanel from '$lib/components/SlidePanel.svelte';
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
	let projectSearchText = $state('');
	let projectDropdownOpen = $state(false);
	let availableHosts = $state<string[]>([]);

	let projectSuggestions = $derived(
		Array.from($projectNames.entries())
			.filter(([id, name]) =>
				projectSearchText.length === 0 ||
				name.toLowerCase().includes(projectSearchText.toLowerCase()) ||
				id.toLowerCase().includes(projectSearchText.toLowerCase())
			)
			.slice(0, 10)
	);

	let filteredInstances = $derived(
		allInstances.filter(i =>
			(!projectFilter || i.project_id === projectFilter)
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
			if (hostFilter) url += `&host=${encodeURIComponent(hostFilter)}`;
			const res = await api.get<PagedResponse<AdminInstance>>(url, token, projectId);
			allInstances = res.items;
			nextMarker = res.next_marker;
		} catch {
			allInstances = [];
		} finally {
			loading = false;
		}
	}

	async function loadHosts() {
		try {
			const hvs = await api.get<{ id: string; name: string }[]>('/api/admin/hypervisors', token, projectId);
			availableHosts = hvs.map(h => h.name).sort();
		} catch {
			availableHosts = [];
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

	function handleDocumentClick(e: MouseEvent) {
		const target = e.target as HTMLElement;
		if (!target.closest('.project-filter-wrapper')) {
			projectDropdownOpen = false;
		}
	}

	onMount(() => {
		load();
		loadTimeseries(tsRange);
		loadHosts();
		projectNames.load(token, projectId);
		document.addEventListener('click', handleDocumentClick);
		return () => document.removeEventListener('click', handleDocumentClick);
	});
</script>

<div class="p-4 md:p-8 max-w-6xl">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-white">전체 인스턴스</h1>
		<div class="flex items-center gap-3">
			<button onclick={() => { markerStack = []; nextMarker = null; hostFilter = ''; projectFilter = ''; load(); loadHosts(); }} class="text-xs text-gray-400 hover:text-white transition-colors px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600">새로고침</button>
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
		<select bind:value={hostFilter} onchange={() => { markerStack = []; nextMarker = null; load(); }} class="bg-gray-800 border border-gray-700 text-sm text-gray-300 rounded-lg px-2 py-1.5 focus:outline-none focus:border-blue-500">
			<option value="">모든 호스트</option>
			{#each availableHosts as h}
				<option value={h}>{h}</option>
			{/each}
		</select>
		<div class="relative project-filter-wrapper">
		<div class="flex items-center bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 w-52 focus-within:border-blue-500">
			<input
				type="text"
				placeholder="프로젝트 검색..."
				bind:value={projectSearchText}
				onfocus={() => (projectDropdownOpen = true)}
				oninput={() => { projectDropdownOpen = true; if (!projectSearchText) { projectFilter = ''; } }}
				class="bg-transparent text-sm text-gray-300 flex-1 outline-none min-w-0"
			/>
			{#if projectFilter}
				<button onclick={() => { projectFilter = ''; projectSearchText = ''; projectDropdownOpen = false; }} class="text-gray-500 hover:text-white ml-1 flex-shrink-0">✕</button>
			{/if}
		</div>
		{#if projectDropdownOpen && projectSuggestions.length > 0}
			<!-- svelte-ignore a11y_no_static_element_interactions -->
			<div
				class="absolute top-full mt-1 left-0 w-64 bg-gray-900 border border-gray-700 rounded-lg shadow-xl z-20 overflow-hidden"
				onmouseleave={() => {}}
			>
				{#each projectSuggestions as [id, name]}
					<button
						class="w-full text-left px-3 py-2 text-xs hover:bg-gray-800 transition-colors {projectFilter === id ? 'bg-blue-900/30 text-blue-400' : 'text-gray-300'}"
						onclick={() => { projectFilter = id; projectSearchText = name; projectDropdownOpen = false; }}
					>
						<div class="font-medium truncate">{name}</div>
						<div class="text-gray-500 font-mono">{id.slice(0, 12)}...</div>
					</button>
				{/each}
			</div>
		{/if}
	</div>
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
	<SlidePanel onClose={closeDetail}>
		<InstanceDetailPanel instanceId={selectedInstanceId} adminProjectId={selectedProjectId} onClose={closeDetail} />
	</SlidePanel>
{/if}