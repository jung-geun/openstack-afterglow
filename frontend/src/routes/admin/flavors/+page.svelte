<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import { projectNames } from '$lib/stores/projectNames';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import FlavorCreateModal from '$lib/components/admin/flavors/FlavorCreateModal.svelte';
	import FlavorManagePanel from '$lib/components/admin/flavors/FlavorManagePanel.svelte';

	interface Flavor {
		id: string;
		name: string;
		vcpus: number;
		ram: number;
		disk: number;
		is_public: boolean;
		description: string | null;
		extra_specs: Record<string, string>;
		is_gpu: boolean;
		gpu_count: number;
	}
	interface PagedResponse<T> {
		items: T[];
		next_marker: string | null;
		count: number;
	}

	let flavors = $state<Flavor[]>([]);
	let loading = $state(true);
	let refreshing = $state(false);
	let pageSize = $state(20);
	let currentPage = $state(0);
	let error = $state('');

	let nameFilter = $state('');
	let vcpuFilter = $state('');
	let ramFilter = $state('');
	let diskFilter = $state('');
	let gpuFilter = $state('');

	let sortColumn = $state('');
	let sortAsc = $state(true);

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

	let filteredFlavors = $derived(
		flavors
			.filter((f) => {
				if (nameFilter && !f.name.toLowerCase().includes(nameFilter.toLowerCase())) return false;
				if (vcpuFilter && f.vcpus !== parseInt(vcpuFilter)) return false;
				if (ramFilter) {
					const ramMB = parseInt(ramFilter);
					if (f.ram < ramMB * 0.9 || f.ram > ramMB * 1.1) return false;
				}
				if (diskFilter) {
					const diskGB = parseInt(diskFilter);
					if (f.disk < diskGB * 0.9 || f.disk > diskGB * 1.1) return false;
				}
				if (gpuFilter === 'yes' && !f.is_gpu) return false;
				if (gpuFilter === 'no' && f.is_gpu) return false;
				return true;
			})
			.toSorted((a, b) => {
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

	$effect(() => {
		nameFilter;
		vcpuFilter;
		ramFilter;
		diskFilter;
		gpuFilter;
		currentPage = 0;
	});

	let pagedFlavors = $derived(
		filteredFlavors.slice(currentPage * pageSize, (currentPage + 1) * pageSize),
	);
	let totalPages = $derived(Math.max(1, Math.ceil(filteredFlavors.length / pageSize)));

	let showCreate = $state(false);
	let selectedFlavor = $state<Flavor | null>(null);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function load() {
		if (flavors.length === 0) loading = true;
		else refreshing = true;
		error = '';
		try {
			const res = await api.get<PagedResponse<Flavor>>(
				'/api/admin/flavors?limit=999',
				token,
				projectId,
			);
			flavors = res.items;
			currentPage = 0;
		} catch (e) {
			error = e instanceof ApiError ? e.message : 'Flavor 목록 조회 실패';
			flavors = [];
		} finally {
			loading = false;
			refreshing = false;
		}
	}

	async function deleteFlavor(id: string) {
		if (!confirm('이 Flavor를 삭제하시겠습니까?')) return;
		try {
			await api.delete(`/api/admin/flavors/${id}`, token, projectId);
			await load();
		} catch (e) {
			alert('Flavor 삭제 실패: ' + (e instanceof ApiError ? e.message : '오류'));
		}
	}

	function formatRam(mb: number): string {
		if (mb >= 1024) return `${(mb / 1024).toFixed(mb % 1024 === 0 ? 0 : 1)} GB`;
		return `${mb} MB`;
	}

	const ar = createAutoRefresh(load, {
		storageKey: 'admin-flavors',
		defaultInterval: 60,
		intervalOptions: [30, 60],
	});

	onMount(() => {
		load();
		projectNames.load(token, projectId);
	});
</script>

<div class="p-4 md:p-8 max-w-7xl mx-auto">
	<PageHeader breadcrumb="COMPUTE / FLAVORS" title="Flavor">
		{#snippet actions()}
			<button
				onclick={() => (showCreate = true)}
				class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-colors"
			>+ 생성</button>
			<AutoRefreshControl
				bind:active={ar.active}
				bind:intervalSeconds={ar.intervalSeconds}
				intervalOptions={ar.intervalOptions}
				refreshing={loading || refreshing}
				onManualRefresh={() => {
					nameFilter = '';
					vcpuFilter = '';
					ramFilter = '';
					diskFilter = '';
					gpuFilter = '';
					load();
				}}
			/>
			<div class="flex items-center gap-1 text-xs text-gray-500">
				표시:
				{#each [10, 20, 30] as n}
					<button
						onclick={() => {
							pageSize = n;
							currentPage = 0;
						}}
						class="px-2 py-0.5 rounded {pageSize === n
							? 'bg-blue-600 text-white'
							: 'bg-gray-800 hover:bg-gray-700 text-gray-400'}"
					>{n}</button>
				{/each}
			</div>
		{/snippet}
	</PageHeader>

	<div class="flex flex-wrap gap-3 mb-4">
		<input
			type="text"
			placeholder="이름 검색"
			bind:value={nameFilter}
			class="bg-gray-800 border border-gray-700 text-sm text-gray-300 rounded-lg px-3 py-1.5 w-40 focus:outline-none focus:border-blue-500"
		/>
		<input
			type="number"
			placeholder="VCPU"
			bind:value={vcpuFilter}
			class="bg-gray-800 border border-gray-700 text-sm text-gray-300 rounded-lg px-3 py-1.5 w-24 focus:outline-none focus:border-blue-500"
		/>
		<input
			type="number"
			placeholder="RAM (MB)"
			bind:value={ramFilter}
			class="bg-gray-800 border border-gray-700 text-sm text-gray-300 rounded-lg px-3 py-1.5 w-28 focus:outline-none focus:border-blue-500"
		/>
		<input
			type="number"
			placeholder="Disk (GB)"
			bind:value={diskFilter}
			class="bg-gray-800 border border-gray-700 text-sm text-gray-300 rounded-lg px-3 py-1.5 w-28 focus:outline-none focus:border-blue-500"
		/>
		<select
			bind:value={gpuFilter}
			class="bg-gray-800 border border-gray-700 text-sm text-gray-300 rounded-lg px-3 py-1.5 focus:outline-none focus:border-blue-500"
		>
			<option value="">GPU 전체</option>
			<option value="yes">GPU 있음</option>
			<option value="no">GPU 없음</option>
		</select>
	</div>

	{#if error}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>
	{/if}

	{#if loading}
		<LoadingSkeleton variant="table" rows={5} />
	{:else}
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
									<div>
										<span class="text-white">{f.name}</span>
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
											onclick={() => (selectedFlavor = f)}
											class="text-blue-400 hover:text-blue-300 text-xs"
										>관리</button>
										<button
											onclick={() => deleteFlavor(f.id)}
											class="text-red-400 hover:text-red-300 text-xs"
										>삭제</button>
									</div>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
			<div class="flex items-center justify-between mt-3">
				<button
					disabled={currentPage === 0}
					onclick={() => {
						currentPage -= 1;
					}}
					class="px-3 py-1.5 text-xs rounded bg-gray-800 hover:bg-gray-700 text-gray-300 disabled:opacity-30 disabled:cursor-not-allowed"
				>← 이전</button>
				<span class="text-xs text-gray-500">
					{filteredFlavors.length}개 중 {currentPage * pageSize + 1}–{Math.min(
						(currentPage + 1) * pageSize,
						filteredFlavors.length,
					)}
					{#if filteredFlavors.length < flavors.length}
						(전체 {flavors.length}개 필터됨)
					{/if}
				</span>
				<button
					disabled={currentPage >= totalPages - 1}
					onclick={() => {
						currentPage += 1;
					}}
					class="px-3 py-1.5 text-xs rounded bg-gray-800 hover:bg-gray-700 text-gray-300 disabled:opacity-30 disabled:cursor-not-allowed"
				>다음 →</button>
			</div>
		</div>
	{/if}
</div>

<FlavorCreateModal bind:open={showCreate} onCreated={load} />

<FlavorManagePanel
	flavor={selectedFlavor}
	onClose={() => (selectedFlavor = null)}
	onChanged={load}
/>
