<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import { formatNumber, formatStorage } from '$lib/utils/format';

	interface Hypervisor {
		id: string;
		name: string;
		state: string;
		status: string;
		vcpus: number;
		vcpus_used: number;
		memory_size_mb: number;
		memory_used_mb: number;
		local_disk_gb: number;
		local_disk_used_gb: number;
		running_vms: number;
	}

	let hypervisors = $state<Hypervisor[]>([]);
	let loading = $state(true);
	let sortColumn = $state('');
	let sortAsc = $state(true);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function load() {
		loading = true;
		try {
			hypervisors = await api.get<Hypervisor[]>('/api/admin/hypervisors', token, projectId);
		} catch {
			hypervisors = [];
		} finally {
			loading = false;
		}
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

	let sortedHypervisors = $derived(
		hypervisors.toSorted((a, b) => {
			if (!sortColumn) return 0;
			let va: string | number;
			let vb: string | number;
			if (sortColumn === 'name') {
				va = a.name;
				vb = b.name;
			} else {
				va = (a as Record<string, number>)[sortColumn] ?? 0;
				vb = (b as Record<string, number>)[sortColumn] ?? 0;
			}
			const cmp = typeof va === 'string' ? va.localeCompare(vb as string) : (va as number) - (vb as number);
			return sortAsc ? cmp : -cmp;
		})
	);

	onMount(load);
</script>

<div class="p-4 md:p-8 max-w-6xl">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-white">하이퍼바이저</h1>
		<button onclick={load} class="text-xs text-gray-400 hover:text-white transition-colors px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600">새로고침</button>
	</div>

	{#if loading}
		<LoadingSkeleton variant="table" rows={5} />
	{:else if hypervisors.length === 0}
		<div class="text-gray-600 text-sm">하이퍼바이저가 없습니다</div>
	{:else}
		<div class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
						<th class="text-left py-2 pr-4">
							<button onclick={() => toggleSort('name')} class="hover:text-white transition-colors flex items-center gap-1">
								호스트명 <span class="text-gray-600">{sortIcon('name')}</span>
							</button>
						</th>
						<th class="text-left py-2 pr-4">상태</th>
						<th class="text-left py-2 pr-4">
							<button onclick={() => toggleSort('running_vms')} class="hover:text-white transition-colors flex items-center gap-1">
								VM <span class="text-gray-600">{sortIcon('running_vms')}</span>
							</button>
						</th>
						<th class="text-left py-2 pr-4">
							<button onclick={() => toggleSort('vcpus_used')} class="hover:text-white transition-colors flex items-center gap-1">
								vCPU <span class="text-gray-600">{sortIcon('vcpus_used')}</span>
							</button>
						</th>
						<th class="text-left py-2 pr-4">
							<button onclick={() => toggleSort('memory_used_mb')} class="hover:text-white transition-colors flex items-center gap-1">
								RAM (GB) <span class="text-gray-600">{sortIcon('memory_used_mb')}</span>
							</button>
						</th>
						<th class="text-left py-2">로컬 디스크</th>
					</tr>
				</thead>
				<tbody>
					{#each sortedHypervisors as h (h.id)}
						<tr class="border-b border-gray-800/50 text-xs">
							<td class="py-2 pr-4 text-white font-mono">{h.name}</td>
							<td class="py-2 pr-4">
								<span class="{h.state === 'up' && h.status === 'enabled' ? 'text-green-400' : 'text-red-400'}">{h.state}/{h.status}</span>
							</td>
							<td class="py-2 pr-4 text-gray-400">{formatNumber(h.running_vms)}</td>
							<td class="py-2 pr-4 text-gray-400">{formatNumber(h.vcpus_used)}/{formatNumber(h.vcpus)}</td>
							<td class="py-2 pr-4 text-gray-400">{formatNumber(Math.round(h.memory_used_mb/1024))}/{formatNumber(Math.round(h.memory_size_mb/1024))}</td>
							<td class="py-2 text-gray-400">{formatStorage(h.local_disk_used_gb)}/{formatStorage(h.local_disk_gb)}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>
