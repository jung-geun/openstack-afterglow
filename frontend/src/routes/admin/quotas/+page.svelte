<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';

	interface Project {
		id: string;
		name: string;
	}
	interface QuotaLimit {
		limit: number;
		in_use: number;
	}
	interface Quotas {
		compute?: {
			instances?: QuotaLimit;
			cores?: QuotaLimit;
			ram?: QuotaLimit;
		};
		volume?: {
			volumes?: QuotaLimit;
			gigabytes?: QuotaLimit;
		};
	}

	let projects = $state<Project[]>([]);
	let selectedProjectId = $state('');
	let selectedProjectName = $state('');
	let projectSearch = $state('');
	let showProjectDropdown = $state(false);
	let quotas = $state<Quotas | null>(null);
	let loading = $state(true);
	let quotaLoading = $state(false);
	let saving = $state(false);
	let saveError = $state('');
	let saveSuccess = $state('');

	// 편집 폼
	let editInstances = $state(0);
	let editCores = $state(0);
	let editRam = $state(0);
	let editVolumes = $state(0);
	let editGigabytes = $state(0);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	let filteredProjects = $derived(
		projectSearch
			? projects.filter(p => p.name.toLowerCase().includes(projectSearch.toLowerCase()))
			: projects
	);

	async function loadProjects() {
		loading = true;
		try {
			const res = await api.get<{ id: string; name: string }[]>('/api/admin/projects/names', token, projectId);
			projects = res || [];
		} catch { projects = []; } finally { loading = false; }
	}

	function selectProject(p: Project) {
		selectedProjectId = p.id;
		selectedProjectName = p.name;
		projectSearch = p.name;
		showProjectDropdown = false;
		loadQuotas();
	}

	async function loadQuotas() {
		if (!selectedProjectId) { quotas = null; return; }
		quotaLoading = true; saveError = ''; saveSuccess = '';
		try {
			quotas = await api.get<Quotas>(`/api/admin/quotas/${selectedProjectId}`, token, projectId);
			editInstances = quotas?.compute?.instances?.limit ?? 0;
			editCores = quotas?.compute?.cores?.limit ?? 0;
			editRam = quotas?.compute?.ram?.limit ?? 0;
			editVolumes = quotas?.volume?.volumes?.limit ?? 0;
			editGigabytes = quotas?.volume?.gigabytes?.limit ?? 0;
		} catch { quotas = null; } finally { quotaLoading = false; }
	}

	async function saveQuotas() {
		if (!selectedProjectId) return;
		saving = true; saveError = ''; saveSuccess = '';
		try {
			await api.put(`/api/admin/quotas/${selectedProjectId}`, {
				instances: editInstances,
				cores: editCores,
				ram: editRam,
				volumes: editVolumes,
				gigabytes: editGigabytes,
			}, token, projectId);
			saveSuccess = '저장되었습니다';
			await loadQuotas();
		} catch (e) { saveError = e instanceof ApiError ? e.message : '저장 실패'; } finally { saving = false; }
	}

	function formatRam(mb: number): string {
		if (mb >= 1024) return `${(mb / 1024).toFixed(mb % 1024 === 0 ? 0 : 1)} GB`;
		return `${mb} MB`;
	}

	onMount(loadProjects);
</script>

<div class="p-4 md:p-8 max-w-6xl">
	<h1 class="text-2xl font-bold text-white mb-6">쿼터 관리</h1>

	{#if loading}
		<LoadingSkeleton variant="table" rows={3} />
	{:else}
		<div class="mb-6 relative max-w-md">
			<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">프로젝트 선택</label>
			<input
				type="text"
				bind:value={projectSearch}
				onfocus={() => showProjectDropdown = true}
				oninput={() => { showProjectDropdown = true; if (!projectSearch) { selectedProjectId = ''; selectedProjectName = ''; quotas = null; } }}
				onblur={() => setTimeout(() => { showProjectDropdown = false; }, 150)}
				placeholder="프로젝트 이름으로 검색..."
				class="w-full bg-gray-800 border border-gray-700 text-sm text-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500"
			/>
			{#if showProjectDropdown && filteredProjects.length > 0}
				<div class="absolute z-10 w-full mt-1 bg-gray-800 border border-gray-700 rounded-lg shadow-xl max-h-60 overflow-y-auto">
					{#each filteredProjects as p (p.id)}
						<button
							type="button"
							onmousedown={() => selectProject(p)}
							class="w-full text-left px-3 py-2 text-sm text-gray-300 hover:bg-gray-700 transition-colors {selectedProjectId === p.id ? 'bg-gray-700 text-white' : ''}"
						>{p.name}</button>
					{/each}
				</div>
			{/if}
			{#if selectedProjectName}
				<div class="mt-1 text-xs text-gray-500">선택됨: <span class="text-blue-400">{selectedProjectName}</span></div>
			{/if}
		</div>

		{#if selectedProjectId}
			{#if quotaLoading}
				<LoadingSkeleton variant="table" rows={3} />
			{:else if quotas}
				{#if saveSuccess}<div class="bg-green-900/40 border border-green-700 text-green-300 rounded-lg px-4 py-3 text-sm mb-4">{saveSuccess}</div>{/if}
				{#if saveError}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{saveError}</div>{/if}

				<!-- Compute Quotas -->
				<div class="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-6">
					<h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-4">Compute 쿼터</h2>
					<div class="grid grid-cols-1 sm:grid-cols-3 gap-6">
						<div>
							<label class="block text-xs text-gray-400 mb-1.5">인스턴스</label>
							<div class="text-sm text-gray-500 mb-1">사용: {quotas?.compute?.instances?.in_use ?? 0}</div>
							<input bind:value={editInstances} type="number" min="-1" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
						</div>
						<div>
							<label class="block text-xs text-gray-400 mb-1.5">CPU 코어</label>
							<div class="text-sm text-gray-500 mb-1">사용: {quotas?.compute?.cores?.in_use ?? 0}</div>
							<input bind:value={editCores} type="number" min="-1" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
						</div>
						<div>
							<label class="block text-xs text-gray-400 mb-1.5">RAM (MB)</label>
							<div class="text-sm text-gray-500 mb-1">사용: {formatRam(quotas?.compute?.ram?.in_use ?? 0)}</div>
							<input bind:value={editRam} type="number" min="-1" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
						</div>
					</div>
				</div>

				<!-- Volume Quotas -->
				<div class="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-6">
					<h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-4">Volume 쿼터</h2>
					<div class="grid grid-cols-1 sm:grid-cols-2 gap-6">
						<div>
							<label class="block text-xs text-gray-400 mb-1.5">볼륨</label>
							<div class="text-sm text-gray-500 mb-1">사용: {quotas?.volume?.volumes?.in_use ?? 0}</div>
							<input bind:value={editVolumes} type="number" min="-1" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
						</div>
						<div>
							<label class="block text-xs text-gray-400 mb-1.5">용량 (GB)</label>
							<div class="text-sm text-gray-500 mb-1">사용: {quotas?.volume?.gigabytes?.in_use ?? 0} GB</div>
							<input bind:value={editGigabytes} type="number" min="-1" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
						</div>
					</div>
				</div>

				<div class="flex justify-end">
					<button onclick={saveQuotas} disabled={saving} class="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg disabled:opacity-30">
						{saving ? '저장 중...' : '저장'}
					</button>
				</div>
			{:else}
				<div class="text-gray-600 text-sm">쿼터를 불러올 수 없습니다</div>
			{/if}
		{/if}
	{/if}
</div>