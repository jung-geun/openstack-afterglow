<script lang="ts">
	import type { Flavor } from '$lib/types/flavor';
	import Pagination from '$lib/components/ui/Pagination.svelte';

	let {
		flavors,
		totalUnfiltered,
		pageSize,
		refreshing,
		onManage,
		onDelete,
	}: {
		flavors: Flavor[];
		totalUnfiltered: number;
		pageSize: number;
		refreshing: boolean;
		onManage: (f: Flavor) => void;
		onDelete: (id: string) => Promise<void>;
	} = $props();

	let sortColumn = $state('');
	let sortAsc = $state(true);
	let currentPage = $state(0);

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

	function formatRam(mb: number): string {
		if (mb >= 1024) return `${(mb / 1024).toFixed(mb % 1024 === 0 ? 0 : 1)} GB`;
		return `${mb} MB`;
	}

	let sortedFlavors = $derived(
		flavors.toSorted((a, b) => {
			if (!sortColumn) return 0;
			let va: string | number, vb: string | number;
			if (sortColumn === 'is_public') {
				va = a.is_public ? 1 : 0;
				vb = b.is_public ? 1 : 0;
			} else {
				va = (a as unknown as Record<string, unknown>)[sortColumn] as string | number;
				vb = (b as unknown as Record<string, unknown>)[sortColumn] as string | number;
			}
			const cmp =
				typeof va === 'string' ? va.localeCompare(vb as string) : (va as number) - (vb as number);
			return sortAsc ? cmp : -cmp;
		}),
	);

	let totalPages = $derived(Math.max(1, Math.ceil(flavors.length / pageSize)));

	let pagedFlavors = $derived(
		sortedFlavors.slice(currentPage * pageSize, (currentPage + 1) * pageSize),
	);

	// Reset to page 0 when flavors list or pageSize changes
	$effect(() => {
		flavors;
		pageSize;
		currentPage = 0;
	});
</script>

<div class:opacity-60={refreshing} class:pointer-events-none={refreshing}>
	<div class="overflow-x-auto">
		<table class="w-full text-sm">
			<thead>
				<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
					<th
						class="text-left py-2 pr-4 cursor-pointer select-none hover:text-gray-200"
						onclick={() => toggleSort('name')}
					>이름 <span class="text-gray-600">{sortIcon('name')}</span></th>
					<th
						class="text-left py-2 pr-4 cursor-pointer select-none hover:text-gray-200"
						onclick={() => toggleSort('vcpus')}
					>VCPU <span class="text-gray-600">{sortIcon('vcpus')}</span></th>
					<th
						class="text-left py-2 pr-4 cursor-pointer select-none hover:text-gray-200"
						onclick={() => toggleSort('ram')}
					>RAM <span class="text-gray-600">{sortIcon('ram')}</span></th>
					<th
						class="text-left py-2 pr-4 cursor-pointer select-none hover:text-gray-200"
						onclick={() => toggleSort('disk')}
					>Disk <span class="text-gray-600">{sortIcon('disk')}</span></th>
					<th
						class="text-left py-2 pr-4 cursor-pointer select-none hover:text-gray-200"
						onclick={() => toggleSort('is_public')}
					>공개 <span class="text-gray-600">{sortIcon('is_public')}</span></th>
					<th class="text-left py-2 pr-4">GPU</th>
					<th class="text-right py-2">액션</th>
				</tr>
			</thead>
			<tbody>
				{#each pagedFlavors as f (f.id)}
					<tr class="border-b border-gray-800/50 text-xs hover:bg-gray-800/50 transition-colors">
						<td class="py-2 pr-4">
							<div class="min-w-0">
								<span class="text-white max-md:block max-md:max-w-[66vw] max-md:truncate" title={f.name}>{f.name}</span>
								{#if f.description}
									<div class="text-gray-500 text-xs mt-0.5">{f.description}</div>
								{/if}
							</div>
						</td>
						<td class="py-2 pr-4 text-gray-300">{f.vcpus}</td>
						<td class="py-2 pr-4 text-gray-300">{formatRam(f.ram)}</td>
						<td class="py-2 pr-4 text-gray-300">{f.disk} GB</td>
						<td class="py-2 pr-4">
							<span
								class="px-1.5 py-0.5 rounded text-xs font-medium {f.is_public
									? 'bg-green-900/30 text-green-400'
									: 'bg-yellow-900/30 text-yellow-400'}"
							>{f.is_public ? 'Public' : 'Private'}</span>
						</td>
						<td class="py-2 pr-4 text-gray-400">
							{#if f.is_gpu}
								<span class="text-purple-400">GPU{f.gpu_count > 1 ? ` x${f.gpu_count}` : ''}</span>
							{:else}
								-
							{/if}
						</td>
						<td class="py-2 text-right">
							<div class="flex items-center justify-end gap-2">
								<button
									onclick={() => onManage(f)}
									class="text-blue-400 hover:text-blue-300 text-xs"
								>관리</button>
								<button
									onclick={() => onDelete(f.id)}
									class="text-red-400 hover:text-red-300 text-xs"
								>삭제</button>
							</div>
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
	<Pagination
		page={currentPage + 1}
		{totalPages}
		total={flavors.length}
		{pageSize}
		hasPrev={currentPage > 0}
		hasNext={currentPage < totalPages - 1}
		onPrev={() => { currentPage -= 1; }}
		onNext={() => { currentPage += 1; }}
		note={flavors.length < totalUnfiltered ? `(전체 ${totalUnfiltered}개 필터됨)` : null}
	/>
</div>
