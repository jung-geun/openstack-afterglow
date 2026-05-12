<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';

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
	interface GpuQuota {
		gpu_type: string;
		limit: number;
		in_use: number;
		available: number;
	}
	interface GpuDefaultQuota {
		gpu_type: string;
		limit: number;
	}

	let projects = $state<Project[]>([]);
	let selectedProjectId = $state('');
	let selectedProjectName = $state('');
	let projectSearch = $state('');
	let showProjectDropdown = $state(false);
	let quotas = $state<Quotas | null>(null);
	let loading = $state(true);
	let refreshing = $state(false);
	let quotaLoading = $state(false);
	let saving = $state(false);
	let saveError = $state('');
	let saveSuccess = $state('');

	// GPU
	let gpuAliases = $state<string[]>([]);
	let gpuQuotas = $state<GpuQuota[]>([]);
	let gpuDefaults = $state<GpuDefaultQuota[]>([]);
	let gpuQuotaLoading = $state(false);
	let gpuQuotaError = $state('');
	let gpuDefaultLoading = $state(false);
	let gpuDefaultError = $state('');
	let gpuDefaultSuccess = $state('');

	// Compute/Volume 편집 폼
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

	// 선택한 프로젝트의 GPU alias별 quota를 맵으로 관리
	let gpuQuotaMap = $derived(
		Object.fromEntries(gpuQuotas.map(q => [q.gpu_type, q]))
	);
	let gpuDefaultMap = $derived(
		Object.fromEntries(gpuDefaults.map(q => [q.gpu_type, q.limit]))
	);

	// aliases + defaults + quotas에서 모든 GPU 타입 합산
	let allGpuTypes = $derived(
		[...new Set([...gpuAliases, ...gpuDefaults.map(d => d.gpu_type), ...gpuQuotas.map(q => q.gpu_type)])].sort()
	);

	async function loadProjects() {
		if (projects.length === 0) loading = true;
		else refreshing = true;
		try {
			const res = await api.get<{ id: string; name: string }[]>('/api/admin/projects/names', token, projectId);
			projects = res || [];
		} catch { projects = []; } finally { loading = false; refreshing = false; }
	}

	async function loadGpuAliases() {
		try {
			const res = await api.get<{ aliases: string[] }>('/api/admin/gpu-aliases', token, projectId);
			gpuAliases = res.aliases ?? [];
		} catch (e) {
			console.warn('[Quotas] GPU alias 로드 실패:', e instanceof ApiError ? e.message : e);
			gpuAliases = [];
		}
	}

	async function loadGpuDefaults() {
		gpuDefaultLoading = true; gpuDefaultError = '';
		try {
			gpuDefaults = await api.get<GpuDefaultQuota[]>('/api/admin/gpu-quotas/defaults', token, projectId);
		} catch (e) {
			gpuDefaultError = e instanceof ApiError ? e.message : '기본 GPU quota 조회 실패';
			gpuDefaults = [];
		} finally { gpuDefaultLoading = false; }
	}

	async function setGpuDefault(gpuType: string, limit: number) {
		gpuDefaultError = ''; gpuDefaultSuccess = '';
		try {
			await api.put('/api/admin/gpu-quotas/defaults', { gpu_type: gpuType, limit }, token, projectId);
			gpuDefaultSuccess = '기본 GPU quota 저장됨';
			await loadGpuDefaults();
			if (selectedProjectId) await loadGpuQuotas();
		} catch (e) {
			gpuDefaultError = e instanceof ApiError ? e.message : '기본 GPU quota 설정 실패';
		}
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
		await loadGpuQuotas();
	}

	async function loadGpuQuotas() {
		if (!selectedProjectId) { gpuQuotas = []; return; }
		gpuQuotaLoading = true; gpuQuotaError = '';
		try {
			gpuQuotas = await api.get<GpuQuota[]>(`/api/admin/gpu-quotas/${selectedProjectId}`, token, projectId);
		} catch (e) {
			gpuQuotaError = e instanceof ApiError ? e.message : 'GPU quota 조회 실패';
			gpuQuotas = [];
		} finally { gpuQuotaLoading = false; }
	}

	async function setGpuQuota(gpuType: string, limit: number) {
		if (!selectedProjectId) return;
		gpuQuotaError = '';
		try {
			await api.put(`/api/admin/gpu-quotas/${selectedProjectId}`, { gpu_type: gpuType, limit }, token, projectId);
			await loadGpuQuotas();
		} catch (e) {
			gpuQuotaError = e instanceof ApiError ? e.message : 'GPU quota 설정 실패';
		}
	}

	async function deleteGpuQuota(gpuType: string) {
		if (!selectedProjectId) return;
		try {
			await api.delete(`/api/admin/gpu-quotas/${selectedProjectId}/${encodeURIComponent(gpuType)}`, token, projectId);
			await loadGpuQuotas();
		} catch (e) {
			gpuQuotaError = e instanceof ApiError ? e.message : 'GPU quota 삭제 실패';
		}
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

	onMount(() => { loadProjects(); loadGpuAliases(); loadGpuDefaults(); });
</script>

<div class="p-4 md:p-8 max-w-7xl mx-auto">
	<PageHeader breadcrumb="IDENTITY / QUOTAS" title="쿼터" />

	{#if loading}
		<LoadingSkeleton variant="table" rows={3} />
	{:else}
		<div class:opacity-60={refreshing} class:pointer-events-none={refreshing}>
		<!-- 전체 프로젝트 기본 GPU Quota -->
		<div class="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-6">
			<h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-1">전체 프로젝트 기본 GPU Quota</h2>
			<p class="text-xs text-gray-600 mb-4">프로젝트별 개별 설정이 없을 때 적용되는 기본값입니다. 미설정 시 0 (GPU VM 생성 불가).</p>
			{#if gpuDefaultError}<div class="text-red-400 text-xs mb-3">{gpuDefaultError}</div>{/if}
			{#if gpuDefaultSuccess}<div class="text-green-400 text-xs mb-3">{gpuDefaultSuccess}</div>{/if}
			{#if gpuDefaultLoading}
				<div class="text-gray-500 text-sm">불러오는 중...</div>
			{:else if allGpuTypes.length === 0}
				<div class="text-gray-600 text-sm">GPU alias를 찾을 수 없습니다. GPU flavor가 등록되어 있는지 확인하세요.</div>
			{:else}
				<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
					{#each allGpuTypes as alias}
						{@const currentLimit = gpuDefaultMap[alias] ?? 0}
						<div class="flex items-center gap-2 bg-gray-800/60 rounded-lg px-3 py-2">
							<span class="text-sm text-white font-mono flex-1">{alias}</span>
							<input
								type="number"
								min="-1"
								value={currentLimit}
								onchange={(e) => setGpuDefault(alias, Number((e.target as HTMLInputElement).value))}
								class="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm text-white text-right focus:outline-none focus:border-blue-500"
							/>
						</div>
					{/each}
				</div>
				<p class="text-xs text-gray-600 mt-2">-1 = 무제한, 0 = 사용 불가</p>
			{/if}
		</div>

		<!-- 프로젝트 선택 -->
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

				<div class="flex justify-end mb-6">
					<button onclick={saveQuotas} disabled={saving} class="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg disabled:opacity-30">
						{saving ? '저장 중...' : '저장'}
					</button>
				</div>

				<!-- GPU Quotas (프로젝트별) -->
				<div class="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-6">
					<h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-1">GPU Quota</h2>
					<p class="text-xs text-gray-600 mb-4">이 프로젝트의 GPU quota입니다. 개별 설정이 없으면 전체 기본값이 적용됩니다.</p>
					{#if gpuQuotaError}<div class="text-red-400 text-xs mb-3">{gpuQuotaError}</div>{/if}
					{#if gpuQuotaLoading}
						<div class="text-gray-500 text-sm">불러오는 중...</div>
					{:else if gpuQuotas.length === 0 && allGpuTypes.length === 0}
						<div class="text-gray-600 text-sm">GPU alias를 찾을 수 없습니다.</div>
					{:else}
						<table class="w-full text-sm">
							<thead>
								<tr class="text-gray-400 text-xs border-b border-gray-800">
									<th class="text-left pb-2">GPU 타입</th>
									<th class="text-right pb-2">기본값</th>
									<th class="text-right pb-2">프로젝트 Limit</th>
									<th class="text-right pb-2">사용 중</th>
									<th class="text-right pb-2">가용</th>
									<th class="text-right pb-2"></th>
								</tr>
							</thead>
							<tbody>
								{#each gpuQuotas as q}
									{@const alias = q.gpu_type}
									{@const defLimit = gpuDefaultMap[alias] ?? 0}
									{@const effectiveLimit = q.limit}
									{@const inUse = q.in_use}
									{@const avail = effectiveLimit === -1 ? -1 : effectiveLimit - inUse}
										<tr class="border-b border-gray-800/50 last:border-0">
											<td class="py-2 text-white font-mono">{alias}</td>
											<td class="py-2 text-right text-gray-500">{defLimit === -1 ? '무제한' : defLimit}</td>
											<td class="py-2 text-right">
												<input
													type="number"
													min="-1"
													value={q?.limit ?? ''}
													placeholder={String(defLimit)}
													onchange={(e) => {
														const v = (e.target as HTMLInputElement).value;
														if (v === '') {
															deleteGpuQuota(alias);
														} else {
															setGpuQuota(alias, Number(v));
														}
													}}
													class="w-20 bg-gray-700 border border-gray-600 rounded px-2 py-1 text-sm text-white text-right focus:outline-none focus:border-blue-500"
												/>
											</td>
											<td class="py-2 text-right text-gray-400">{inUse}</td>
											<td class="py-2 text-right {avail > 0 ? 'text-green-400' : avail === -1 ? 'text-gray-500' : 'text-red-400'}">
												{effectiveLimit === -1 ? '무제한' : avail}
											</td>
											<td class="py-2 text-right">
												{#if q?.limit != null}
													<button
														onclick={() => deleteGpuQuota(alias)}
														class="text-xs text-gray-500 hover:text-gray-300 transition-colors"
														title="프로젝트별 설정 삭제 (기본값으로 복귀)"
													>초기화</button>
												{/if}
											</td>
										</tr>
									{/each}
								</tbody>
							</table>
							<p class="text-xs text-gray-600 mt-2">빈 칸 = 기본값 사용, -1 = 무제한, 0 = 사용 불가</p>
					{/if}
				</div>
			{:else}
				<div class="text-gray-600 text-sm">쿼터를 불러올 수 없습니다</div>
			{/if}
		{/if}
		</div>
	{/if}
</div>
