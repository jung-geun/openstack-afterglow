<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import { projectNames } from '$lib/stores/projectNames';

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
		project_name: string;
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

	// 정렬
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
			.filter(f => {
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
					va = (a as Record<string, unknown>)[sortColumn] as string | number;
					vb = (b as Record<string, unknown>)[sortColumn] as string | number;
				}
				const cmp = typeof va === 'string' ? va.localeCompare(vb as string) : (va as number) - (vb as number);
				return sortAsc ? cmp : -cmp;
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
	let accessError = $state('');
	let selectedProjectId = $state('');
	let projectSearch = $state('');

	// extra_specs 관리
	let activeTab = $state<'access' | 'properties'>('access');
	let newSpecKey = $state('');
	let newSpecValue = $state('');
	let specSaving = $state(false);
	let specError = $state('');
	let editingSpecKey = $state<string | null>(null);
	let editingSpecValue = $state('');

	// 프로젝트 목록 (접근 관리용)
	let allProjects = $state<{ id: string; name: string }[]>([]);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	// 이미 접근 권한이 있는 프로젝트 ID 집합
	let accessedProjectIds = $derived(new Set(accessList.map(a => a.project_id)));
	let availableProjects = $derived(allProjects.filter(p => !accessedProjectIds.has(p.id)));
	let searchedProjects = $derived(
		projectSearch.trim().length > 0
			? availableProjects.filter(p =>
				p.name.toLowerCase().includes(projectSearch.toLowerCase()) ||
				p.id.toLowerCase().includes(projectSearch.toLowerCase())
			).slice(0, 8)
			: []
	);

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
		selectedProjectId = '';
		projectSearch = '';
		activeTab = 'access';
		newSpecKey = '';
		newSpecValue = '';
		specError = '';
		editingSpecKey = null;
		editingSpecValue = '';
		await loadAccess();
		if (allProjects.length === 0) {
			try {
				allProjects = await api.get<{ id: string; name: string }[]>('/api/admin/projects/names', token, projectId);
			} catch { allProjects = []; }
		}
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

	async function addAccess(pid?: string) {
		const targetId = pid || selectedProjectId;
		if (!selectedFlavor || !targetId) return;
		accessError = '';
		try {
			await api.post(`/api/admin/flavors/${selectedFlavor.id}/access`, { project_id: targetId }, token, projectId);
			selectedProjectId = '';
			projectSearch = '';
			await loadAccess();
		} catch (e) {
			accessError = e instanceof ApiError ? e.message : '접근 권한 추가 실패';
		}
	}

	async function removeAccess(pid: string) {
		if (!selectedFlavor) return;
		try {
			await api.delete(`/api/admin/flavors/${selectedFlavor.id}/access/${pid}`, token, projectId);
			await loadAccess();
		} catch {
			accessError = '접근 권한 제거 실패';
		}
	}

	async function addExtraSpec() {
		if (!selectedFlavor || !newSpecKey.trim()) return;
		specSaving = true;
		specError = '';
		try {
			await api.post(`/api/admin/flavors/${selectedFlavor.id}/extra-specs`, {
				key: newSpecKey.trim(),
				value: newSpecValue.trim(),
			}, token, projectId);
			// 로컬 상태 즉시 업데이트
			selectedFlavor = {
				...selectedFlavor,
				extra_specs: { ...selectedFlavor.extra_specs, [newSpecKey.trim()]: newSpecValue.trim() },
			};
			newSpecKey = '';
			newSpecValue = '';
			// 전체 목록도 갱신
			await load();
		} catch (e) {
			specError = e instanceof ApiError ? e.message : 'extra_spec 추가 실패';
		} finally {
			specSaving = false;
		}
	}

	function startEditSpec(key: string, value: string) {
		editingSpecKey = key;
		editingSpecValue = value;
	}

	function cancelEditSpec() {
		editingSpecKey = null;
		editingSpecValue = '';
	}

	async function saveEditSpec() {
		if (!selectedFlavor || !editingSpecKey) return;
		specSaving = true;
		specError = '';
		try {
			await api.post(`/api/admin/flavors/${selectedFlavor.id}/extra-specs`, {
				key: editingSpecKey,
				value: editingSpecValue.trim(),
			}, token, projectId);
			selectedFlavor = {
				...selectedFlavor,
				extra_specs: { ...selectedFlavor.extra_specs, [editingSpecKey]: editingSpecValue.trim() },
			};
			editingSpecKey = null;
			editingSpecValue = '';
			await load();
		} catch (e) {
			specError = e instanceof ApiError ? e.message : 'extra_spec 수정 실패';
		} finally {
			specSaving = false;
		}
	}

	async function deleteExtraSpec(key: string) {
		if (!selectedFlavor) return;
		specError = '';
		try {
			await api.delete(`/api/admin/flavors/${selectedFlavor.id}/extra-specs/${encodeURIComponent(key)}`, token, projectId);
			const specs = { ...selectedFlavor.extra_specs };
			delete specs[key];
			selectedFlavor = { ...selectedFlavor, extra_specs: specs };
			await load();
		} catch (e) {
			specError = e instanceof ApiError ? e.message : 'extra_spec 삭제 실패';
		}
	}

	function closeAccess() {
		selectedFlavor = null;
		accessList = [];
		accessError = '';
		selectedProjectId = '';
	}

	function formatRam(mb: number): string {
		if (mb >= 1024) return `${(mb / 1024).toFixed(mb % 1024 === 0 ? 0 : 1)} GB`;
		return `${mb} MB`;
	}

	onMount(() => {
		load();
		projectNames.load(token, projectId);
	});
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
						<th class="text-left py-2 pr-4 cursor-pointer select-none hover:text-gray-200" onclick={() => toggleSort('name')}>
							이름 <span class="text-gray-600">{sortIcon('name')}</span>
						</th>
						<th class="text-left py-2 pr-4 cursor-pointer select-none hover:text-gray-200" onclick={() => toggleSort('vcpus')}>
							VCPU <span class="text-gray-600">{sortIcon('vcpus')}</span>
						</th>
						<th class="text-left py-2 pr-4 cursor-pointer select-none hover:text-gray-200" onclick={() => toggleSort('ram')}>
							RAM <span class="text-gray-600">{sortIcon('ram')}</span>
						</th>
						<th class="text-left py-2 pr-4 cursor-pointer select-none hover:text-gray-200" onclick={() => toggleSort('disk')}>
							Disk <span class="text-gray-600">{sortIcon('disk')}</span>
						</th>
						<th class="text-left py-2 pr-4 cursor-pointer select-none hover:text-gray-200" onclick={() => toggleSort('is_public')}>
							공개 <span class="text-gray-600">{sortIcon('is_public')}</span>
						</th>
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
									<button onclick={() => openAccessPanel(f)} class="text-blue-400 hover:text-blue-300 text-xs">관리</button>
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

<!-- 관리 패널 (접근 + 속성) -->
{#if selectedFlavor}
	<div class="fixed inset-0 z-40" role="dialog" aria-modal="true" onkeydown={(e) => e.key === 'Escape' && closeAccess()} tabindex="-1">
		<button class="absolute inset-0 bg-black/50 cursor-default" onclick={closeAccess} aria-label="패널 닫기"></button>
		<div class="absolute right-0 top-14 bottom-0 w-full md:w-[640px] bg-gray-950 border-l border-gray-700 overflow-y-auto shadow-2xl p-6">
			<div class="flex items-center justify-between mb-4">
				<h2 class="text-lg font-semibold text-white">Flavor 관리</h2>
				<button onclick={closeAccess} class="text-gray-400 hover:text-white text-xl">&times;</button>
			</div>
			<div class="mb-4">
				<div class="text-sm text-gray-400">Flavor</div>
				<div class="text-white font-medium">{selectedFlavor.name}</div>
				<div class="text-xs text-gray-500">{selectedFlavor.vcpus} VCPU / {formatRam(selectedFlavor.ram)} / {selectedFlavor.disk} GB</div>
			</div>

			<!-- 탭 -->
			<div class="flex border-b border-gray-800 mb-4">
				<button
					onclick={() => activeTab = 'access'}
					class="px-4 py-2 text-sm {activeTab === 'access' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-gray-400 hover:text-gray-200'}"
				>접근 관리</button>
				<button
					onclick={() => activeTab = 'properties'}
					class="px-4 py-2 text-sm {activeTab === 'properties' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-gray-400 hover:text-gray-200'}"
				>속성 (extra_specs)</button>
			</div>

			{#if activeTab === 'access'}
				<!-- 접근 관리 탭 -->
				{#if selectedFlavor.is_public}
					<div class="bg-gray-800/50 border border-gray-700 text-gray-400 rounded-lg px-4 py-6 text-sm text-center">
						Public Flavor는 모든 프로젝트에서 사용 가능하므로 접근 권한 설정이 필요하지 않습니다.
					</div>
				{:else}
				{#if accessError}
					<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-3 py-2 text-xs mb-3">{accessError}</div>
				{/if}

				<div class="mb-4">
					<div class="text-sm text-gray-400 mb-2">프로젝트 접근 추가</div>
					<div class="relative">
						<input
							type="text"
							placeholder="프로젝트 이름 또는 ID 검색..."
							bind:value={projectSearch}
							class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-1.5 text-white text-sm focus:outline-none focus:border-blue-500"
						/>
						{#if searchedProjects.length > 0}
							<div class="absolute z-10 left-0 right-0 mt-1 bg-gray-800 border border-gray-700 rounded-lg shadow-xl overflow-hidden">
								{#each searchedProjects as p}
									<div class="flex items-center justify-between px-3 py-2 hover:bg-gray-700 border-b border-gray-700/50 last:border-0">
										<div>
											<span class="text-sm text-white">{p.name}</span>
											<span class="text-xs text-gray-500 ml-2 font-mono">{p.id.slice(0, 12)}</span>
										</div>
										<button
											onclick={() => addAccess(p.id)}
											class="text-xs px-2 py-0.5 bg-blue-600 hover:bg-blue-500 text-white rounded ml-2"
										>추가</button>
									</div>
								{/each}
							</div>
						{:else if projectSearch.trim().length > 0}
							<div class="absolute z-10 left-0 right-0 mt-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-xs text-gray-500">
								일치하는 프로젝트가 없습니다
							</div>
						{/if}
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
								<div>
									<div class="text-xs text-gray-200">{a.project_name || a.project_id}</div>
									{#if a.project_name}
										<div class="text-xs text-gray-600 font-mono">{a.project_id.slice(0, 12)}</div>
									{/if}
								</div>
								<button onclick={() => removeAccess(a.project_id)} class="text-red-400 hover:text-red-300 text-xs">제거</button>
							</div>
						{/each}
					</div>
				{/if}
				{/if}
			{:else}
				<!-- 속성 탭 -->
				{#if specError}
					<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-3 py-2 text-xs mb-3">{specError}</div>
				{/if}

				{#if Object.keys(selectedFlavor.extra_specs).length === 0}
					<div class="text-gray-600 text-sm mb-4">등록된 속성이 없습니다</div>
				{:else}
					<div class="space-y-1 mb-4">
						{#each Object.entries(selectedFlavor.extra_specs) as [k, v]}
							<div class="bg-gray-900 border border-gray-800 rounded-lg px-3 py-2">
								{#if editingSpecKey === k}
									<div class="flex items-center gap-2">
										<span class="text-xs text-blue-300 font-mono break-all shrink-0">{k}</span>
										<span class="text-gray-500">=</span>
										<input
											bind:value={editingSpecValue}
											type="text"
											class="flex-1 min-w-0 bg-gray-800 border border-blue-500 rounded px-2 py-1 text-xs text-white font-mono focus:outline-none"
											onkeydown={(e) => { if (e.key === 'Enter') saveEditSpec(); if (e.key === 'Escape') cancelEditSpec(); }}
										/>
										<button onclick={saveEditSpec} disabled={specSaving} class="text-green-400 hover:text-green-300 text-xs shrink-0">저장</button>
										<button onclick={cancelEditSpec} class="text-gray-400 hover:text-gray-300 text-xs shrink-0">취소</button>
									</div>
								{:else}
									<div class="flex items-center justify-between">
										<button class="flex-1 min-w-0 text-left cursor-pointer hover:bg-gray-800/50 rounded -mx-1 px-1 py-0.5 transition-colors" onclick={() => startEditSpec(k, v)}>
											<span class="text-xs text-blue-300 font-mono break-all">{k}</span>
											<span class="text-gray-500 mx-2">=</span>
											<span class="text-xs text-gray-300 font-mono break-all">{v}</span>
										</button>
										<button onclick={() => deleteExtraSpec(k)} class="ml-2 text-red-400 hover:text-red-300 text-xs shrink-0">삭제</button>
									</div>
								{/if}
							</div>
						{/each}
					</div>
				{/if}

				<div class="text-sm text-gray-400 mb-2">속성 추가/수정</div>
				<div class="space-y-2">
					<input
						bind:value={newSpecKey}
						type="text"
						placeholder="키 (예: hw:numa_nodes)"
						class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-1.5 text-white text-sm font-mono focus:outline-none focus:border-blue-500"
					/>
					<input
						bind:value={newSpecValue}
						type="text"
						placeholder="값"
						class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-1.5 text-white text-sm font-mono focus:outline-none focus:border-blue-500"
					/>
					<button
						onclick={addExtraSpec}
						disabled={specSaving || !newSpecKey.trim()}
						class="w-full px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg disabled:opacity-30"
					>
						{specSaving ? '저장 중...' : '추가/수정'}
					</button>
				</div>
			{/if}
		</div>
	</div>
{/if}
