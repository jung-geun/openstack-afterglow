<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import TimeSeriesChart from '$lib/components/TimeSeriesChart.svelte';
	import { formatNumber } from '$lib/utils/format';
	import { projectNames } from '$lib/stores/projectNames';

	interface AdminFileStorage {
		id: string;
		name: string;
		status: string;
		size: number;
		share_proto: string;
		metadata: Record<string, string>;
		project_id: string | null;
		created_at: string | null;
		export_locations: string[];
	}

	const statusColor: Record<string, string> = {
		available: 'text-green-400', creating: 'text-yellow-400',
		deleting: 'text-orange-400', error: 'text-red-400',
	};

	interface TsPoint { ts: number; total?: number; [key: string]: number | undefined; }

	let fileStorages = $state<AdminFileStorage[]>([]);
	let loading = $state(true);
	let tsData = $state<TsPoint[]>([]);
	let tsRange = $state('7d');
	let tsLoading = $state(true);
	let pageSize = $state(20);
	let currentPage = $state(0);
	let copiedId = $state<string | null>(null);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	const totalPages = $derived(Math.ceil(fileStorages.length / pageSize));
	const displayedStorages = $derived(
		fileStorages.slice(currentPage * pageSize, (currentPage + 1) * pageSize)
	);

	function formatDate(iso: string | null): string {
		if (!iso) return '-';
		return iso.slice(0, 10);
	}

	function copyId(id: string) {
		navigator.clipboard.writeText(id);
		copiedId = id;
		setTimeout(() => { copiedId = null; }, 1500);
	}

	async function loadTimeseries(range: string) {
		tsLoading = true;
		try {
			tsData = await api.get<TsPoint[]>(`/api/admin/timeseries/file_storage?range=${range}`, token, projectId);
		} catch {
			tsData = [];
		} finally {
			tsLoading = false;
		}
	}

	async function load() {
		loading = true;
		currentPage = 0;
		try {
			fileStorages = await api.get<AdminFileStorage[]>('/api/admin/all-file-storages', token, projectId);
		} catch {
			fileStorages = [];
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		load();
		loadTimeseries(tsRange);
		projectNames.load(token, projectId);
	});
</script>

<div class="p-4 md:p-8 max-w-6xl">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-white">전체 파일 스토리지</h1>
		<div class="flex items-center gap-3">
			<select
				bind:value={pageSize}
				onchange={() => { currentPage = 0; }}
				class="text-xs bg-gray-800 border border-gray-700 text-gray-300 rounded px-2 py-1.5"
			>
				{#each [10, 20, 30, 50] as s}
					<option value={s}>{s}개</option>
				{/each}
			</select>
			<button onclick={load} class="text-xs text-gray-400 hover:text-white transition-colors px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600">새로고침</button>
		</div>
	</div>

	<div class="mb-6">
		{#if tsLoading}
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-5 h-48 flex items-center justify-center">
				<div class="text-gray-600 text-sm">차트 로딩 중...</div>
			</div>
		{:else}
			<TimeSeriesChart
				data={tsData}
				title="파일 스토리지 수 추이"
				mainKey="total"
				currentRange={tsRange}
				onRangeChange={(r) => { tsRange = r; loadTimeseries(r); }}
			/>
		{/if}
	</div>

	{#if loading}
		<LoadingSkeleton variant="table" rows={5} />
	{:else if fileStorages.length === 0}
		<div class="text-gray-600 text-sm">파일 스토리지가 없습니다</div>
	{:else}
		<div class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
						<th class="text-left py-2 pr-4">이름</th>
						<th class="text-left py-2 pr-4">상태</th>
						<th class="text-left py-2 pr-4">크기</th>
						<th class="text-left py-2 pr-4">프로토콜</th>
						<th class="text-left py-2 pr-4">유형</th>
						<th class="text-left py-2 pr-4">프로젝트</th>
						<th class="text-left py-2 pr-4">생성일</th>
						<th class="text-left py-2">Export 경로</th>
					</tr>
				</thead>
				<tbody>
					{#each displayedStorages as fs (fs.id)}
						<tr class="border-b border-gray-800/50 text-xs hover:bg-gray-800/20">
							<td class="py-2 pr-4 text-white font-medium">{fs.name || fs.id.slice(0, 8)}</td>
							<td class="py-2 pr-4 {statusColor[fs.status] ?? 'text-gray-400'}">{fs.status}</td>
							<td class="py-2 pr-4 text-gray-400">{formatNumber(fs.size)} GB</td>
							<td class="py-2 pr-4">
								<span class="px-1.5 py-0.5 rounded text-xs font-medium {fs.share_proto === 'NFS' ? 'bg-blue-900/40 text-blue-300' : 'bg-purple-900/40 text-purple-300'}">{fs.share_proto}</span>
							</td>
							<td class="py-2 pr-4 text-gray-500">{fs.metadata?.union_type || '-'}</td>
							<td class="py-2 pr-4">
								{#if fs.project_id}
									<div class="flex items-center gap-1.5">
										<span class="text-gray-300">{$projectNames.get(fs.project_id) ?? fs.project_id.slice(0, 8)}</span>
										<button
											onclick={() => copyId(fs.project_id!)}
											class="text-gray-600 hover:text-gray-400 transition-colors"
											title={fs.project_id}
										>
											{#if copiedId === fs.project_id}
												<svg class="w-3 h-3 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
											{:else}
												<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path></svg>
											{/if}
										</button>
									</div>
								{:else}
									<span class="text-gray-600">-</span>
								{/if}
							</td>
							<td class="py-2 pr-4 text-gray-400">{formatDate(fs.created_at)}</td>
							<td class="py-2 text-gray-500 font-mono">
								{#if fs.export_locations?.length > 0}
									<div class="flex items-center gap-1.5">
										<span class="truncate max-w-[200px]" title={fs.export_locations[0]}>{fs.export_locations[0]}</span>
										<button
											onclick={() => copyId(fs.export_locations[0])}
											class="text-gray-600 hover:text-gray-400 transition-colors shrink-0"
										>
											{#if copiedId === fs.export_locations[0]}
												<svg class="w-3 h-3 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
											{:else}
												<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path></svg>
											{/if}
										</button>
									</div>
								{:else}
									<span>-</span>
								{/if}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>

		{#if totalPages > 1}
			<div class="flex items-center justify-between mt-4 text-xs text-gray-500">
				<span>{fileStorages.length}개 중 {currentPage * pageSize + 1}–{Math.min((currentPage + 1) * pageSize, fileStorages.length)}개</span>
				<div class="flex gap-2">
					<button
						onclick={() => { currentPage--; }}
						disabled={currentPage === 0}
						class="px-3 py-1 rounded border border-gray-700 hover:border-gray-600 disabled:opacity-30 disabled:cursor-not-allowed"
					>이전</button>
					<span class="px-3 py-1 text-gray-400">{currentPage + 1} / {totalPages}</span>
					<button
						onclick={() => { currentPage++; }}
						disabled={currentPage >= totalPages - 1}
						class="px-3 py-1 rounded border border-gray-700 hover:border-gray-600 disabled:opacity-30 disabled:cursor-not-allowed"
					>다음</button>
				</div>
			</div>
		{/if}
	{/if}
</div>
