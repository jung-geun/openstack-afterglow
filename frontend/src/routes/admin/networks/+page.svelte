<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api } from '$lib/api/client';
	import TimeSeriesChart from '$lib/components/TimeSeriesChart.svelte';

	interface NetworkInfo {
		id: string;
		name: string;
		status: string;
		subnets: string[];
		is_external: boolean;
		is_shared: boolean;
	}
	interface TsPoint {
		ts: number;
		total?: number;
		[key: string]: number | undefined;
	}

	let networks = $state<NetworkInfo[]>([]);
	let loading = $state(true);
	let tsData = $state<TsPoint[]>([]);
	let tsRange = $state('7d');
	let tsLoading = $state(true);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function loadNetworks() {
		loading = true;
		try {
			networks = await api.get<NetworkInfo[]>('/api/admin/all-networks', token, projectId);
		} catch {
			networks = [];
		} finally {
			loading = false;
		}
	}

	async function loadTimeseries(range: string) {
		tsLoading = true;
		try {
			tsData = await api.get<TsPoint[]>(`/api/admin/timeseries/networks?range=${range}`, token, projectId);
		} catch {
			tsData = [];
		} finally {
			tsLoading = false;
		}
	}

	onMount(() => { loadNetworks(); loadTimeseries(tsRange); });
</script>

<div class="p-4 md:p-8 max-w-6xl">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-white">전체 네트워크</h1>
		<button onclick={loadNetworks} class="text-xs text-gray-400 hover:text-white px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600">새로고침</button>
	</div>

	<div class="mb-6">
		{#if tsLoading}
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-5 h-48 flex items-center justify-center">
				<div class="text-gray-600 text-sm">차트 로딩 중...</div>
			</div>
		{:else}
			<TimeSeriesChart
				data={tsData}
				title="네트워크 수 추이"
				mainKey="total"
				extraKeys={['routers', 'floating_ips_used']}
				currentRange={tsRange}
				onRangeChange={(r) => { tsRange = r; loadTimeseries(r); }}
			/>
		{/if}
	</div>

	{#if loading}
		<div class="text-gray-500 text-sm">로딩 중...</div>
	{:else}
		<div class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
						<th class="text-left py-2 pr-4">이름</th>
						<th class="text-left py-2 pr-4">상태</th>
						<th class="text-left py-2 pr-4">유형</th>
						<th class="text-left py-2">서브넷</th>
					</tr>
				</thead>
				<tbody>
					{#each networks as n (n.id)}
						<tr class="border-b border-gray-800/50 text-xs">
							<td class="py-2 pr-4 text-white">{n.name || n.id.slice(0, 8)}</td>
							<td class="py-2 pr-4 {n.status === 'ACTIVE' ? 'text-green-400' : 'text-gray-400'}">{n.status}</td>
							<td class="py-2 pr-4">
								{#if n.is_external}<span class="px-1.5 py-0.5 bg-orange-900/30 text-orange-300 rounded text-xs mr-1">외부</span>{/if}
								{#if n.is_shared}<span class="px-1.5 py-0.5 bg-blue-900/30 text-blue-300 rounded text-xs">공유</span>{/if}
								{#if !n.is_external && !n.is_shared}<span class="text-gray-500">내부</span>{/if}
							</td>
							<td class="py-2 text-gray-500">{n.subnets.length}개</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		<div class="mt-3 text-xs text-gray-600">총 {networks.length}개 네트워크</div>
	{/if}
</div>
