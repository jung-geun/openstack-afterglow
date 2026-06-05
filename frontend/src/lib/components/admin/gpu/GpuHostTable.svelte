<script lang="ts">
	import type { AggregatedHost } from '$lib/types/gpu';

	let {
		hosts,
	}: {
		hosts: AggregatedHost[];
	} = $props();

	let expandedHost = $state<string | null>(null);
	let sortColumn = $state('');
	let sortAsc = $state(true);

	function toggleHost(name: string) {
		expandedHost = expandedHost === name ? null : name;
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

	let sortedHosts = $derived(
		hosts.toSorted((a, b) => {
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
				va = (a as unknown as Record<string, number>)[sortColumn] ?? 0;
				vb = (b as unknown as Record<string, number>)[sortColumn] ?? 0;
			}
			return sortAsc ? va - vb : vb - va;
		})
	);
</script>

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
			{#each sortedHosts as h (h.name)}
				<tr class="border-b border-gray-800/50 text-xs hover:bg-gray-800/50 transition-colors cursor-pointer" onclick={() => toggleHost(h.name)}>
					<td class="py-2 pr-4 text-white font-medium"><span class="max-md:block max-md:max-w-[66vw] max-md:truncate" title={h.name}>{h.name}</span></td>
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
									<div class="h-1.5 rounded-full transition-all" style="width: {Math.round(h.gpu_used / h.gpu_total * 100)}%; background: var(--gradient-usage)"></div>
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
