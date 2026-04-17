<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';

	interface GpuDevice {
		provider_name: string;
		provider_uuid: string;
		pci_address: string;
		resource_class: string;
		vendor_id: string;
		vendor_name: string;
		device_id: string;
		device_name: string;
		total: number;
		used: number;
		allocation_ratio: number;
		reserved: number;
	}

	interface GpuHost {
		name: string;
		uuid: string;
		gpus: GpuDevice[];
		gpu_total: number;
		gpu_used: number;
	}

	interface GpuGroup {
		device_name: string;
		vendor_name: string;
		total: number;
		used: number;
	}

	interface AggregatedHost {
		name: string;
		gpus: GpuDevice[];
		gpu_groups: GpuGroup[];
		gpu_total: number;
		gpu_used: number;
	}

	interface GpuType {
		device_name: string;
		vendor: string;
		total: number;
		used: number;
	}

	interface GpuResponse {
		hosts: GpuHost[];
		aggregated_hosts: AggregatedHost[];
		summary: {
			total_hosts: number;
			total_gpus: number;
			used_gpus: number;
			available_gpus: number;
		};
		gpu_types: GpuType[];
	}

	let aggregatedHosts = $state<AggregatedHost[]>([]);
	let summary = $state({ total_hosts: 0, total_gpus: 0, used_gpus: 0, available_gpus: 0 });
	let gpuTypes = $state<GpuType[]>([]);
	let loading = $state(true);
	let error = $state('');
	let expandedHost = $state<string | null>(null);
	let sortColumn = $state('');
	let sortAsc = $state(true);
	let availableFilter = $state<'all' | 'available' | 'full'>('all');
	let selectedGpuTypes = $state<Set<string>>(new Set());

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function load() {
		loading = true;
		error = '';
		try {
			const res = await api.get<GpuResponse>('/api/admin/gpu-hosts', token, projectId);
			aggregatedHosts = res.aggregated_hosts ?? [];
			summary = res.summary;
			gpuTypes = res.gpu_types ?? [];
		} catch (e) {
			error = e instanceof ApiError ? e.message : 'GPU 정보를 불러올 수 없습니다';
			hosts = [];
		} finally {
			loading = false;
		}
	}

	function toggleHost(name: string) {
		expandedHost = expandedHost === name ? null : name;
	}

	function toggleGpuType(deviceName: string) {
		const next = new Set(selectedGpuTypes);
		if (next.has(deviceName)) next.delete(deviceName);
		else next.add(deviceName);
		selectedGpuTypes = next;
	}

	function toggleSort(col: string) {
		if (sortColumn === col) {
			sortAsc = !sortAsc;
		} else {
			sortColumn = col;
			sortAsc = true;
		}
	}

	function sortIcon(col: string): string {
		if (sortColumn !== col) return '↕';
		return sortAsc ? '↑' : '↓';
	}

	let filteredHosts = $derived(
		aggregatedHosts
			.filter((h) => {
				if (availableFilter === 'available' && h.gpu_total - h.gpu_used <= 0) return false;
				if (availableFilter === 'full' && h.gpu_total - h.gpu_used !== 0) return false;
				if (selectedGpuTypes.size > 0 && !h.gpu_groups.some(g => selectedGpuTypes.has(g.device_name))) return false;
				return true;
			})
			.toSorted((a, b) => {
				if (!sortColumn) return 0;
				if (sortColumn === 'name') {
					const cmp = a.name.localeCompare(b.name);
					return sortAsc ? cmp : -cmp;
				}
				let va: number;
				let vb: number;
				if (sortColumn === 'usage') {
					va = a.gpu_total > 0 ? a.gpu_used / a.gpu_total : 0;
					vb = b.gpu_total > 0 ? b.gpu_used / b.gpu_total : 0;
				} else if (sortColumn === 'available') {
					va = a.gpu_total - a.gpu_used;
					vb = b.gpu_total - b.gpu_used;
				} else {
					va = (a as Record<string, number>)[sortColumn] ?? 0;
					vb = (b as Record<string, number>)[sortColumn] ?? 0;
				}
				return sortAsc ? va - vb : vb - va;
			})
	);

	onMount(load);
</script>

<div class="p-4 md:p-8 max-w-6xl">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-white">GPU 모니터링</h1>
		<button onclick={() => load()} class="text-xs text-gray-400 hover:text-white transition-colors px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600">새로고침</button>
	</div>

	{#if error}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>
	{/if}

	{#if loading}
		<LoadingSkeleton variant="table" rows={5} />
	{:else}
		<!-- 요약 카드 -->
		<div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
				<div class="text-xs text-gray-400 uppercase tracking-wide mb-1">전체 GPU</div>
				<div class="text-2xl font-bold text-white">{summary.total_gpus}</div>
				<div class="text-xs text-gray-500 mt-1">{summary.total_hosts}개 호스트</div>
			</div>
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
				<div class="text-xs text-gray-400 uppercase tracking-wide mb-1">사용 중</div>
				<div class="text-2xl font-bold text-red-400">{summary.used_gpus}</div>
				<div class="text-xs text-gray-500 mt-1">{summary.total_gpus > 0 ? Math.round(summary.used_gpus / summary.total_gpus * 100) : 0}% 사용률</div>
			</div>
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
				<div class="text-xs text-gray-400 uppercase tracking-wide mb-1">사용 가능</div>
				<div class="text-2xl font-bold text-green-400">{summary.available_gpus}</div>
				<div class="text-xs text-gray-500 mt-1">할당 가능</div>
			</div>
		</div>

		<!-- GPU 종류별 요약 -->
		{#if gpuTypes.length > 0}
			<div class="mb-6">
				<div class="text-xs text-gray-400 uppercase tracking-wide mb-2">GPU 종류별 현황</div>
				<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
					{#each gpuTypes as gt}
						<button
							onclick={() => toggleGpuType(gt.device_name)}
							class="bg-gray-900 border rounded-lg px-4 py-3 flex items-center justify-between text-left transition-colors {selectedGpuTypes.has(gt.device_name) ? 'border-blue-500 bg-blue-900/20' : 'border-gray-800 hover:border-gray-600'}"
						>
							<div>
								<div class="text-sm font-medium text-white flex items-center gap-1.5">
									{gt.device_name}
									{#if selectedGpuTypes.has(gt.device_name)}
										<span class="text-xs bg-blue-600 text-white px-1 rounded">선택됨</span>
									{/if}
								</div>
								<div class="text-xs text-gray-500">{gt.vendor}</div>
							</div>
							<div class="text-right">
								<div class="text-sm font-semibold text-white">{gt.total}</div>
								{#if gt.used > 0}
									<div class="text-xs text-red-400">{gt.used} 사용 중</div>
								{/if}
								{#if gt.total - gt.used > 0}
									<div class="text-xs text-green-400">{gt.total - gt.used} 사용 가능</div>
								{:else if gt.used === 0}
									<div class="text-xs text-gray-500">0 사용 중</div>
								{/if}
							</div>
						</button>
					{/each}
				</div>
			</div>
		{/if}

		<!-- 호스트별 GPU 테이블 -->
		<div class="flex items-center gap-2 mb-3 flex-wrap">
			<span class="text-xs text-gray-500">필터:</span>
			<button
				onclick={() => (availableFilter = 'all')}
				class="text-xs px-2.5 py-1 rounded transition-colors {availableFilter === 'all' ? 'bg-gray-700 text-white' : 'text-gray-400 hover:text-white'}"
			>전체</button>
			<button
				onclick={() => (availableFilter = 'available')}
				class="text-xs px-2.5 py-1 rounded transition-colors {availableFilter === 'available' ? 'bg-green-900/50 text-green-400' : 'text-gray-400 hover:text-white'}"
			>사용 가능</button>
			<button
				onclick={() => (availableFilter = 'full')}
				class="text-xs px-2.5 py-1 rounded transition-colors {availableFilter === 'full' ? 'bg-red-900/50 text-red-400' : 'text-gray-400 hover:text-white'}"
			>모두 사용 중</button>
			{#if selectedGpuTypes.size > 0}
				<span class="text-gray-600 text-xs">|</span>
				<span class="text-xs text-blue-400">GPU 필터: {Array.from(selectedGpuTypes).join(', ')}</span>
				<button onclick={() => (selectedGpuTypes = new Set())} class="text-xs text-gray-500 hover:text-white transition-colors">✕ 초기화</button>
			{/if}
		</div>
		<div class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
						<th class="text-left py-2 pr-4">
							<button onclick={() => toggleSort('name')} class="hover:text-white transition-colors flex items-center gap-1">
								호스트 <span class="text-gray-600">{sortIcon('name')}</span>
							</button>
						</th>
						<th class="text-left py-2 pr-4">GPU 구성</th>
						<th class="text-center py-2 pr-4">
							<button onclick={() => toggleSort('gpu_total')} class="hover:text-white transition-colors flex items-center gap-1 mx-auto">
								전체 <span class="text-gray-600">{sortIcon('gpu_total')}</span>
							</button>
						</th>
						<th class="text-center py-2 pr-4">
							<button onclick={() => toggleSort('gpu_used')} class="hover:text-white transition-colors flex items-center gap-1 mx-auto">
								사용 중 <span class="text-gray-600">{sortIcon('gpu_used')}</span>
							</button>
						</th>
						<th class="text-center py-2 pr-4">
							<button onclick={() => toggleSort('available')} class="hover:text-white transition-colors flex items-center gap-1 mx-auto">
								사용 가능 <span class="text-gray-600">{sortIcon('available')}</span>
							</button>
						</th>
						<th class="text-center py-2">
							<button onclick={() => toggleSort('usage')} class="hover:text-white transition-colors flex items-center gap-1 mx-auto">
								사용률 <span class="text-gray-600">{sortIcon('usage')}</span>
							</button>
						</th>
					</tr>
				</thead>
				<tbody>
					{#each filteredHosts as h (h.name)}
						<tr class="border-b border-gray-800/50 text-xs hover:bg-gray-800/50 transition-colors cursor-pointer" onclick={() => toggleHost(h.name)}>
							<td class="py-2 pr-4 text-white font-medium">{h.name}</td>
							<td class="py-2 pr-4 text-gray-400">
								{#each h.gpu_groups as g}
									<span class="mr-2">{g.device_name} x{g.total}</span>
								{/each}
							</td>
							<td class="py-2 pr-4 text-center text-gray-300">{h.gpu_total}</td>
							<td class="py-2 pr-4 text-center">
								<span class="{h.gpu_used > 0 ? 'text-red-400' : 'text-gray-500'}">{h.gpu_used}</span>
							</td>
							<td class="py-2 pr-4 text-center">
								<span class="text-green-400">{h.gpu_total - h.gpu_used}</span>
							</td>
							<td class="py-2 text-center">
								{#if h.gpu_total > 0}
									<div class="flex items-center justify-center gap-2">
										<div class="w-16 bg-gray-800 rounded-full h-1.5">
											<div class="bg-blue-500 h-1.5 rounded-full" style="width: {Math.round(h.gpu_used / h.gpu_total * 100)}%"></div>
										</div>
										<span class="text-gray-400">{Math.round(h.gpu_used / h.gpu_total * 100)}%</span>
									</div>
								{:else}
									<span class="text-gray-600">-</span>
								{/if}
							</td>
						</tr>
						{#if expandedHost === h.name}
							<tr>
								<td colspan="6" class="p-0">
									<div class="bg-gray-900/50 border border-gray-800 rounded-lg m-2 p-4">
										<div class="text-xs text-gray-400 uppercase tracking-wide mb-3">GPU 장치 상세</div>
										<div class="space-y-2">
											{#each h.gpus as gpu (gpu.provider_uuid)}
												<div class="flex items-center justify-between bg-gray-800/50 border border-gray-700/50 rounded-lg px-3 py-2">
													<div class="flex items-center gap-4">
														<div>
															<div class="text-xs text-gray-300 font-mono">{gpu.pci_address}</div>
															<div class="text-xs text-gray-500">{gpu.resource_class}</div>
														</div>
														<div class="text-xs text-gray-400">
															<span class="text-gray-300">{gpu.vendor_name}</span>
															{#if gpu.device_name}
																<span class="text-gray-300 ml-1">{gpu.device_name}</span>
															{:else if gpu.device_id}
																<span class="text-gray-500 ml-1">({gpu.device_id})</span>
															{/if}
														</div>
													</div>
													<div class="flex items-center gap-3">
														<span class="px-1.5 py-0.5 rounded text-xs font-medium {gpu.used > 0 ? 'bg-red-900/30 text-red-400' : 'bg-green-900/30 text-green-400'}">
															{gpu.used > 0 ? '사용 중' : '사용 가능'}
														</span>
													</div>
												</div>
											{/each}
										</div>
									</div>
								</td>
							</tr>
						{/if}
					{/each}
				</tbody>
			</table>
		</div>

		{#if aggregatedHosts.length === 0}
			<div class="text-center text-gray-500 text-sm py-8">GPU가 있는 호스트가 없습니다</div>
		{:else if filteredHosts.length === 0}
			<div class="text-center text-gray-500 text-sm py-8">조건에 맞는 호스트가 없습니다</div>
		{/if}
	{/if}
</div>