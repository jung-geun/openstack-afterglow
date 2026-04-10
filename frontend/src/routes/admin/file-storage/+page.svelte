<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import TimeSeriesChart from '$lib/components/TimeSeriesChart.svelte';
	import { formatNumber } from '$lib/utils/format';

	interface AdminFileStorage {
		id: string;
		name: string;
		status: string;
		size: number;
		share_proto: string;
		metadata: Record<string, string>;
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

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

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
		try {
			fileStorages = await api.get<AdminFileStorage[]>('/api/admin/all-file-storages', token, projectId);
		} catch {
			fileStorages = [];
		} finally {
			loading = false;
		}
	}

	onMount(() => { load(); loadTimeseries(tsRange); });
</script>

<div class="p-4 md:p-8 max-w-6xl">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-white">전체 파일 스토리지</h1>
		<button onclick={load} class="text-xs text-gray-400 hover:text-white transition-colors px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600">새로고침</button>
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
						<th class="text-left py-2">유형</th>
					</tr>
				</thead>
				<tbody>
					{#each fileStorages as fs (fs.id)}
						<tr class="border-b border-gray-800/50 text-xs">
							<td class="py-2 pr-4 text-white">{fs.name || fs.id.slice(0, 8)}</td>
							<td class="py-2 pr-4 {statusColor[fs.status] ?? 'text-gray-400'}">{fs.status}</td>
							<td class="py-2 pr-4 text-gray-400">{formatNumber(fs.size)} GB</td>
							<td class="py-2 pr-4 text-gray-400">{fs.share_proto}</td>
							<td class="py-2 text-gray-500">{fs.metadata?.union_type || '-'}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>
