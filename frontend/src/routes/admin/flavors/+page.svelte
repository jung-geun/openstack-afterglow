<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';

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
	interface FlavorAccess {
		flavor_id: string;
		project_id: string;
	}
	interface PagedResponse<T> {
		items: T[];
		next_marker: string | null;
		count: number;
	}

	let flavors = $state<Flavor[]>([]);
	let loading = $state(true);
	let pageSize = $state(20);
	let markerStack = $state<string[]>([]);
	let nextMarker = $state<string | null>(null);
	let error = $state('');

	// 필터
	let nameFilter = $state('');
	let vcpuFilter = $state('');
	let ramFilter = $state('');
	let diskFilter = $state('');
	let gpuFilter = $state('');

	let filteredFlavors = $derived(
		flavors.filter(f => {
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
	);

	// 생성 모달
	let showCreate = $state(false);
	let creating = $state(false);
	let createError = $state('');
	let form = $state({ name: '', vcpus: 1, ram: 512, disk: 0, is_public: true });

	// 접근 관리 패널
	let selectedFlavor = $state<Flavor | null>(null);
	let accessList = $state<FlavorAccess[]>([]);
	let accessLoading = $state(false);
	let addProjectId = $state('');
	let accessError = $state('');

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function load(marker?: string) {
		loading = true;
		error = '';
		try {
			let url = `/api/admin/flavors?limit=${pageSize}`;
			if (marker) url += `&marker=${marker}`;
			const res = await api.get<PagedResponse<Flavor>>(url, token, projectId);
			flavors = res.items;
			nextMarker = res.next_marker;
		} catch (e) {
			error = e instanceof ApiError ? e.message : 'Flavor 목록 조회 실패';
			flavors = [];
		} finally {
			loading = false;
		}
	}

	async function createFlavor() {
		creating = true;
		createError = '';
		try {
			await api.post('/api/admin/flavors', {
				name: form.name,
				vcpus: form.vcpus,
				ram: form.ram,
				disk: form.disk,
				is_public: form.is_public,
			}, token, projectId);
			showCreate = false;
			form = { name: '', vcpus: 1, ram: 512, disk: 0, is_public: true };
			await load();
		} catch (e) {
			createError = e instanceof ApiError ? e.message : 'Flavor 생성 실패';
		} finally {
			creating = false;
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

	async function openAccessPanel(flavor: Flavor) {
		selectedFlavor = flavor;
		accessError = '';
		addProjectId = '';
		await loadAccess();
	}

	async function loadAccess() {
		if (!selectedFlavor) return;
		accessLoading = true;
		try {
			accessList = await api.get<FlavorAccess[]>(`/api/admin/flavors/${selectedFlavor.id}/access`, token, projectId);
		} catch {
			accessList = [];
		} finally {
			accessLoading = false;
		}
	}

	async function addAccess() {
		if (!selectedFlavor || !addProjectId.trim()) return;
		accessError = '';
		try {
			await api.post(`/api/admin/flavors/${selectedFlavor.id}/access`, { project_id: addProjectId.trim() }, token, projectId);
			addProjectId = '';
			await loadAccess();
		} catch (e) {
			accessError = e instanceof ApiError ? e.message : '접근 권한 추가 실패';
		}
	}

	async function removeAccess(projectIdToRemove: string) {
		if (!selectedFlavor) return;
		try {
			await api.delete(`/api/admin/flavors/${selectedFlavor.id}/access/${projectIdToRemove}`, token, projectId);
			await loadAccess();
		} catch {
			accessError = '접근 권한 제거 실패';
		}
	}

	function closeAccess() {
		selectedFlavor = null;
		accessList = [];
		accessError = '';
		addProjectId = '';
	}

	function formatRam(mb: number): string {
		if (mb >= 1024) return `${(mb / 1024).toFixed(mb % 1024 === 0 ? 0 : 1)} GB`;
		return `${mb} MB`;
	}

	onMount(load);
</script>

<div class="p-4 md:p-8 max-w-6xl">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-white">Flavor 관리</h1>
		<div class="flex items-center gap-3">
			<button onclick={() => { showCreate = true; createError = ''; }} class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-colors">+ 생성</button>
			<button onclick={() => { nameFilter = ''; vcpuFilter = ''; ramFilter = ''; diskFilter = ''; gpuFilter = ''; load(); }} class="text-xs text-gray-400 hover:text-white transition-colors px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600">새로고침</button>
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
		<div class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
						<th class="text-left py-2 pr-4">이름</th>
						<th class="text-left py-2 pr-4">VCPU</th>
						<th class="text-left py-2 pr-4">RAM</th>
						<th class="text-left py-2 pr-4">Disk</th>
						<th class="text-left py-2 pr-4">공개</th>
						<th class="text-left py-2 pr-4">GPU</th>
						<th class="text-right py-2">액션</th>
					</tr>
				</thead>
				<tbody>
					{#each filteredFlavors as f (f.id)}
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
								<span class="px-1.5 py-0.5 rounded text-xs font-medium {f.is_public ? 'bg-green-900/30 text-green-400' : 'bg-yellow-900/30 text-yellow-400'}">{f.is_public ? 'Public' : 'Private'}</span>
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
									{#if !f.is_public}
										<button onclick={() => openAccessPanel(f)} class="text-blue-400 hover:text-blue-300 text-xs">접근</button>
									{/if}
									<button onclick={() => deleteFlavor(f.id)} class="text-red-400 hover:text-red-300 text-xs">삭제</button>
								</div>
							</td>
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
					load(nextMarker || undefined);
				}}
				class="px-3 py-1.5 text-xs rounded bg-gray-800 hover:bg-gray-700 text-gray-300 disabled:opacity-30 disabled:cursor-not-allowed"
			>다음 →</button>
		</div>
	{/if}
</div>

<!-- 생성 모달 -->
{#if showCreate}
	<div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onclick={() => { showCreate = false; createError = ''; }} role="dialog" aria-modal="true" onkeydown={(e) => e.key === 'Escape' && (showCreate = false)} tabindex="-1">
		<div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()}>
			<h2 class="text-lg font-semibold text-white mb-5">Flavor 생성</h2>
			{#if createError}
				<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{createError}</div>
			{/if}
			<div class="space-y-4">
				<div>
					<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름</label>
					<input bind:value={form.name} type="text" placeholder="flavor 이름" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
				</div>
				<div class="grid grid-cols-3 gap-3">
					<div>
						<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">VCPU</label>
						<input bind:value={form.vcpus} type="number" min="1" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
					</div>
					<div>
						<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">RAM (MB)</label>
						<input bind:value={form.ram} type="number" min="0" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
					</div>
					<div>
						<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">Disk (GB)</label>
						<input bind:value={form.disk} type="number" min="0" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
					</div>
				</div>
				<div class="flex items-center gap-3">
					<label class="text-sm text-gray-300">공개 여부</label>
					<button
						onclick={() => form.is_public = !form.is_public}
						class="relative w-11 h-6 rounded-full transition-colors {form.is_public ? 'bg-blue-600' : 'bg-gray-700'}"
					>
						<span class="absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform {form.is_public ? 'translate-x-5' : ''}"></span>
					</button>
					<span class="text-xs text-gray-400">{form.is_public ? 'Public' : 'Private'}</span>
				</div>
			</div>
			<div class="flex justify-end gap-3 mt-6">
				<button onclick={() => { showCreate = false; createError = ''; }} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">취소</button>
				<button onclick={createFlavor} disabled={creating || !form.name} class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg disabled:opacity-30">
					{creating ? '생성 중...' : '생성'}
				</button>
			</div>
		</div>
	</div>
{/if}

<!-- 접근 관리 패널 -->
{#if selectedFlavor}
	<div class="fixed inset-0 z-40" role="dialog" aria-modal="true" onkeydown={(e) => e.key === 'Escape' && closeAccess()} tabindex="-1">
		<button class="absolute inset-0 bg-black/50 cursor-default" onclick={closeAccess} aria-label="패널 닫기"></button>
		<div class="absolute right-0 top-14 bottom-0 w-full md:w-[400px] bg-gray-950 border-l border-gray-700 overflow-y-auto shadow-2xl p-6">
			<div class="flex items-center justify-between mb-4">
				<h2 class="text-lg font-semibold text-white">접근 관리</h2>
				<button onclick={closeAccess} class="text-gray-400 hover:text-white text-xl">&times;</button>
			</div>
			<div class="mb-4">
				<div class="text-sm text-gray-400">Flavor</div>
				<div class="text-white font-medium">{selectedFlavor.name}</div>
				<div class="text-xs text-gray-500">{selectedFlavor.vcpus} VCPU / {formatRam(selectedFlavor.ram)} / {selectedFlavor.disk} GB</div>
			</div>

			{#if accessError}
				<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-3 py-2 text-xs mb-3">{accessError}</div>
			{/if}

			<div class="mb-4">
				<div class="text-sm text-gray-400 mb-2">프로젝트 접근 추가</div>
				<div class="flex gap-2">
					<input
						bind:value={addProjectId}
						type="text"
						placeholder="프로젝트 ID"
						class="flex-1 bg-gray-800 border border-gray-600 rounded-lg px-3 py-1.5 text-white text-sm focus:outline-none focus:border-blue-500"
					/>
					<button onclick={addAccess} class="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded-lg">추가</button>
				</div>
			</div>

			<div class="text-sm text-gray-400 mb-2">접근 권한이 있는 프로젝트</div>
			{#if accessLoading}
				<div class="text-gray-500 text-sm">로딩 중...</div>
			{:else if accessList.length === 0}
				<div class="text-gray-600 text-sm">접근 권한이 없습니다</div>
			{:else}
				<div class="space-y-2">
					{#each accessList as a (a.project_id)}
						<div class="flex items-center justify-between bg-gray-900 border border-gray-800 rounded-lg px-3 py-2">
							<span class="text-xs text-gray-300 font-mono">{a.project_id}</span>
							<button onclick={() => removeAccess(a.project_id)} class="text-red-400 hover:text-red-300 text-xs">제거</button>
						</div>
					{/each}
				</div>
			{/if}
		</div>
	</div>
{/if}