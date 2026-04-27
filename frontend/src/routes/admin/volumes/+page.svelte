<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import SlidePanel from '$lib/components/SlidePanel.svelte';
	import TimeSeriesChart from '$lib/components/TimeSeriesChart.svelte';
	import { formatNumber } from '$lib/utils/format';
	import { projectNames } from '$lib/stores/projectNames';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import StatusChip from '$lib/components/ui/StatusChip.svelte';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';

	interface AdminVolume {
		id: string;
		name: string;
		status: string;
		size: number;
		project_id: string | null;
		created_at: string | null;
	}
	interface PagedResponse<T> {
		items: T[];
		next_marker: string | null;
		count: number;
	}

	interface TsPoint { ts: number; total?: number; in_use?: number; available?: number; [key: string]: number | undefined; }

	let allVolumes = $state<AdminVolume[]>([]);
	let loading = $state(true);
	let pageSize = $state(20);
	let markerStack = $state<string[]>([]);
	let nextMarker = $state<string | null>(null);
	let tsData = $state<TsPoint[]>([]);
	let tsRange = $state('7d');
	let tsLoading = $state(true);

	// 수정 모달
	let editVolume = $state<AdminVolume | null>(null);
	let editName = $state('');
	let editDesc = $state('');
	let updating = $state(false);
	let editError = $state('');

	// 삭제 확인
	let deleteVolume = $state<AdminVolume | null>(null);
	let deleting = $state(false);
	let deleteError = $state('');
	let copiedProjectId = $state<string | null>(null);
	function copyProjectId(id: string) {
		navigator.clipboard.writeText(id).then(() => {
			copiedProjectId = id;
			setTimeout(() => { copiedProjectId = null; }, 1500);
		});
	}

	// 용량 확장 모달
	let extendVolume = $state<AdminVolume | null>(null);
	let newSize = $state(0);
	let extending = $state(false);
	let extendError = $state('');

	// 상태 초기화 모달
	let resetVolume = $state<AdminVolume | null>(null);
	let resetStatus = $state('available');
	let resetting = $state(false);
	let resetError = $state('');

	// 강제 삭제 모달
	let forceDeleteVolume = $state<AdminVolume | null>(null);
	let forceDeleting = $state(false);
	let forceDeleteError = $state('');

	// 볼륨 이전 모달
	let transferVolume = $state<AdminVolume | null>(null);
	let transferSearch = $state('');
	let transferProjectId = $state('');
	let transferProjectName = $state('');
	let showTransferDropdown = $state(false);
	let transferring = $state(false);
	let transferError = $state('');
	let allProjects = $state<{ id: string; name: string }[]>([]);

	// 상세 패널
	let selectedVolumeId = $state<string | null>(null);

	// 필터
	let projectFilter = $state('');
	let projectSearchText = $state('');
	let projectDropdownOpen = $state(false);
	let statusFilter = $state('');
	let nameSearch = $state('');
	let nameDebounceTimer = $state<ReturnType<typeof setTimeout> | null>(null);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	let projectSuggestions = $derived(
		Array.from($projectNames.entries())
			.filter(([id, name]) =>
				projectSearchText.length === 0 ||
				name.toLowerCase().includes(projectSearchText.toLowerCase()) ||
				id.toLowerCase().includes(projectSearchText.toLowerCase())
			)
			.slice(0, 10)
	);

	function handleDocumentClick(e: MouseEvent) {
		const target = e.target as HTMLElement;
		if (!target.closest('.project-filter-wrapper')) {
			projectDropdownOpen = false;
		}
	}

	let filteredTransferProjects = $derived(
		transferSearch
			? allProjects.filter(p => p.name.toLowerCase().includes(transferSearch.toLowerCase()))
			: allProjects
	);

	async function loadTimeseries(range: string) {
		tsLoading = true;
		try {
			tsData = await api.get<TsPoint[]>(`/api/admin/timeseries/volumes?range=${range}`, token, projectId);
		} catch {
			tsData = [];
		} finally {
			tsLoading = false;
		}
	}

	async function load(marker?: string) {
		loading = true;
		try {
			let url = `/api/admin/all-volumes?limit=${pageSize}`;
			if (marker) url += `&marker=${marker}`;
			if (projectFilter) url += `&project_id=${encodeURIComponent(projectFilter)}`;
			if (statusFilter) url += `&status=${encodeURIComponent(statusFilter)}`;
			if (nameSearch) url += `&name=${encodeURIComponent(nameSearch)}`;
			const res = await api.get<PagedResponse<AdminVolume>>(url, token, projectId);
			allVolumes = res.items;
			nextMarker = res.next_marker;
		} catch {
			allVolumes = [];
		} finally {
			loading = false;
		}
	}

	async function updateVolume() {
		if (!editVolume) return;
		updating = true; editError = '';
		try {
			await api.patch(`/api/admin/volumes/${editVolume.id}`, { name: editName }, token, projectId);
			editVolume = null; await load();
		} catch (e) { editError = e instanceof ApiError ? e.message : '수정 실패'; } finally { updating = false; }
	}

	async function confirmDelete() {
		if (!deleteVolume) return;
		deleting = true; deleteError = '';
		try {
			await api.delete(`/api/admin/volumes/${deleteVolume.id}`, token, projectId);
			deleteVolume = null; await load();
		} catch (e) { deleteError = e instanceof ApiError ? e.message : '삭제 실패'; } finally { deleting = false; }
	}

	async function confirmExtend() {
		if (!extendVolume) return;
		extending = true; extendError = '';
		try {
			await api.post(`/api/admin/volumes/${extendVolume.id}/extend`, { new_size: newSize }, token, projectId);
			extendVolume = null; await load();
		} catch (e) { extendError = e instanceof ApiError ? e.message : '확장 실패'; } finally { extending = false; }
	}

	async function confirmReset() {
		if (!resetVolume) return;
		resetting = true; resetError = '';
		try {
			await api.post(`/api/admin/volumes/${resetVolume.id}/reset-status`, { status: resetStatus }, token, projectId);
			resetVolume = null; await load(markerStack[markerStack.length - 1]);
		} catch (e) { resetError = e instanceof ApiError ? e.message : '상태 초기화 실패'; } finally { resetting = false; }
	}

	async function confirmForceDelete() {
		if (!forceDeleteVolume) return;
		forceDeleting = true; forceDeleteError = '';
		try {
			await api.post(`/api/admin/volumes/${forceDeleteVolume.id}/force-delete`, {}, token, projectId);
			forceDeleteVolume = null; await load(markerStack[markerStack.length - 1]);
		} catch (e) {
			forceDeleteError = e instanceof ApiError ? e.message : '강제 삭제 실패';
		} finally { forceDeleting = false; }
	}

	async function loadProjects() {
		try {
			allProjects = await api.get<{ id: string; name: string }[]>('/api/admin/projects/names', token, projectId);
		} catch { allProjects = []; }
	}

	async function confirmTransfer() {
		if (!transferVolume || !transferProjectId) return;
		transferring = true; transferError = '';
		try {
			await api.post(`/api/admin/volumes/${transferVolume.id}/transfer`, { target_project_id: transferProjectId }, token, projectId);
			transferVolume = null;
			await load(markerStack[markerStack.length - 1]);
		} catch (e) { transferError = e instanceof ApiError ? e.message : '이전 실패'; } finally { transferring = false; }
	}

	const ar = createAutoRefresh(
		() => { load(markerStack[markerStack.length - 1]); loadTimeseries(tsRange); },
		{ storageKey: 'admin-volumes', defaultActive: true, defaultInterval: 30, intervalOptions: [15, 30, 60] }
	);

	onMount(() => {
		load();
		loadTimeseries(tsRange);
		projectNames.load(token, projectId);
		loadProjects();
		document.addEventListener('click', handleDocumentClick);
		return () => document.removeEventListener('click', handleDocumentClick);
	});
</script>

<div class="p-4 md:p-8 max-w-6xl">
	<PageHeader breadcrumb="STORAGE / VOLUMES" title="전체 볼륨">
		{#snippet actions()}
			<AutoRefreshControl
				bind:active={ar.active}
				bind:intervalSeconds={ar.intervalSeconds}
				intervalOptions={ar.intervalOptions}
				refreshing={loading}
				onManualRefresh={() => { markerStack = []; nextMarker = null; projectFilter = ''; projectSearchText = ''; statusFilter = ''; nameSearch = ''; load(); }}
			/>
			<div class="flex items-center gap-1 text-xs text-gray-500">
				표시:
				{#each [10, 20, 30] as n}
					<button
						onclick={() => { pageSize = n; markerStack = []; nextMarker = null; load(); }}
						class="px-2 py-0.5 rounded {pageSize === n ? 'bg-blue-600 text-white' : 'bg-gray-800 hover:bg-gray-700 text-gray-400'}"
					>{n}</button>
				{/each}
			</div>
		{/snippet}
	</PageHeader>

	<div class="mb-6">
		{#if tsLoading}
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-5 h-48 flex items-center justify-center">
				<div class="text-gray-600 text-sm">차트 로딩 중...</div>
			</div>
		{:else}
			<TimeSeriesChart
				data={tsData}
				title="볼륨 수 추이"
				mainKey="total"
				extraKeys={['in_use', 'available']}
				currentRange={tsRange}
				onRangeChange={(r) => { tsRange = r; loadTimeseries(r); }}
			/>
		{/if}
	</div>

	<!-- 필터 -->
	<div class="flex flex-wrap gap-3 mb-4">
		<select bind:value={statusFilter} onchange={() => { markerStack = []; nextMarker = null; load(); }} class="bg-gray-800 border border-gray-700 text-sm text-gray-300 rounded-lg px-2 py-1.5 focus:outline-none focus:border-blue-500">
			<option value="">모든 상태</option>
			{#each ['available', 'in-use', 'error', 'error_deleting', 'creating', 'deleting', 'attaching', 'detaching', 'reserved'] as s}
				<option value={s}>{s}</option>
			{/each}
		</select>
		<input
			type="text"
			placeholder="이름 검색..."
			bind:value={nameSearch}
			oninput={() => {
				if (nameDebounceTimer) clearTimeout(nameDebounceTimer);
				nameDebounceTimer = setTimeout(() => { markerStack = []; nextMarker = null; load(); }, 300);
			}}
			class="bg-gray-800 border border-gray-700 text-sm text-gray-300 rounded-lg px-3 py-1.5 w-40 focus:outline-none focus:border-blue-500"
		/>
		<div class="relative project-filter-wrapper">
			<div class="flex items-center bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 w-52 focus-within:border-blue-500">
				<input
					type="text"
					placeholder="프로젝트 검색..."
					bind:value={projectSearchText}
					onfocus={() => (projectDropdownOpen = true)}
					oninput={() => { projectDropdownOpen = true; if (!projectSearchText) { projectFilter = ''; } }}
					class="bg-transparent text-sm text-gray-300 flex-1 outline-none min-w-0"
				/>
				{#if projectFilter}
					<button onclick={() => { projectFilter = ''; projectSearchText = ''; projectDropdownOpen = false; markerStack = []; nextMarker = null; load(); }} class="text-gray-500 hover:text-white ml-1 flex-shrink-0">✕</button>
				{/if}
			</div>
			{#if projectDropdownOpen && projectSuggestions.length > 0}
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<div
					class="absolute top-full mt-1 left-0 w-64 bg-gray-900 border border-gray-700 rounded-lg shadow-xl z-20 overflow-hidden"
					onmouseleave={() => {}}
				>
					{#each projectSuggestions as [id, name]}
						<button
							class="w-full text-left px-3 py-2 text-xs hover:bg-gray-800 transition-colors {projectFilter === id ? 'bg-blue-900/30 text-blue-400' : 'text-gray-300'}"
							onclick={() => { projectFilter = id; projectSearchText = name; projectDropdownOpen = false; markerStack = []; nextMarker = null; load(); }}
						>
							<div class="font-medium truncate">{name}</div>
							<div class="text-gray-500 font-mono">{id.slice(0, 12)}...</div>
						</button>
					{/each}
				</div>
			{/if}
		</div>
	</div>

	{#if loading}
		<LoadingSkeleton variant="table" rows={5} />
	{:else}
		<div class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
						<th class="text-left py-2 pr-4">이름</th>
						<th class="text-left py-2 pr-4">상태</th>
						<th class="text-left py-2 pr-4">크기</th>
						<th class="text-left py-2 pr-4">프로젝트</th>
						<th class="text-left py-2 pr-4">생성일</th>
						<th class="text-left py-2">액션</th>
					</tr>
				</thead>
				<tbody>
					{#each allVolumes as v (v.id)}
						<tr
							onclick={() => { selectedVolumeId = v.id; }}
							class="border-b border-gray-800/50 text-xs hover:bg-gray-800/30 transition-colors cursor-pointer {selectedVolumeId === v.id ? 'bg-gray-800/50' : ''}"
						>
							<td class="py-2 pr-4 text-white">{v.name || v.id.slice(0, 8)}</td>
							<td class="py-2 pr-4"><StatusChip status={v.status} /></td>
							<td class="py-2 pr-4 text-gray-400">{formatNumber(v.size)} GB</td>
							<td class="py-2 pr-4">
								<button
									onclick={(e) => { e.stopPropagation(); if (v.project_id) copyProjectId(v.project_id); }}
									class="text-gray-400 hover:text-blue-400 transition-colors cursor-pointer text-left"
									title={v.project_id ?? ''}
								>
									{#if copiedProjectId === v.project_id}
										<span class="text-green-400 text-xs">복사됨</span>
									{:else}
										<span class="text-xs">{v.project_id ? ($projectNames.get(v.project_id) ?? v.project_id.slice(0, 8)) : '-'}</span>
									{/if}
								</button>
							</td>
							<td class="py-2 pr-4 text-gray-500">{v.created_at?.slice(0, 10) ?? '-'}</td>
							<td class="py-2" onclick={(e) => e.stopPropagation()}>
								<div class="flex items-center gap-1">
									<button onclick={() => { editVolume = v; editName = v.name; editDesc = ''; editError = ''; }}
										class="px-2 py-0.5 text-xs bg-gray-700 hover:bg-gray-600 text-gray-300 rounded">수정</button>
									<button onclick={() => { extendVolume = v; newSize = v.size + 10; extendError = ''; }}
										class="px-2 py-0.5 text-xs bg-blue-900/40 hover:bg-blue-800/40 text-blue-400 rounded">확장</button>
									{#if v.status === 'available'}
										<button onclick={() => { transferVolume = v; transferSearch = ''; transferProjectId = ''; transferProjectName = ''; transferError = ''; }}
											class="px-2 py-0.5 text-xs bg-purple-900/40 hover:bg-purple-800/40 text-purple-400 rounded">이전</button>
									{/if}
									<button onclick={() => { resetVolume = v; resetStatus = 'available'; resetError = ''; }}
										class="px-2 py-0.5 text-xs bg-yellow-900/40 hover:bg-yellow-800/40 text-yellow-400 rounded">상태변경</button>
									{#if /^(error|deleting)/i.test(v.status ?? '')}
										<button onclick={() => { forceDeleteVolume = v; forceDeleteError = ''; }}
											class="px-2 py-0.5 text-xs bg-rose-900/40 hover:bg-rose-800/40 text-rose-400 rounded border border-rose-700">강제삭제</button>
									{/if}
									<button onclick={() => { deleteVolume = v; deleteError = ''; }}
										class="px-2 py-0.5 text-xs bg-red-900/30 hover:bg-red-900/50 text-red-400 rounded">삭제</button>
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
					load(nextMarker);
				}}
				class="px-3 py-1.5 text-xs rounded bg-gray-800 hover:bg-gray-700 text-gray-300 disabled:opacity-30 disabled:cursor-not-allowed"
			>다음 →</button>
		</div>
	{/if}
</div>

<!-- 수정 모달 -->
{#if editVolume}
	<div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onclick={() => { editVolume = null; }} role="dialog" onkeydown={(e) => e.key === 'Escape' && (editVolume = null)} tabindex="-1">
		<div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()}>
			<h2 class="text-lg font-semibold text-white mb-5">볼륨 수정</h2>
			{#if editError}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{editError}</div>{/if}
			<div class="space-y-4">
				<div><label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름</label><input bind:value={editName} type="text" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" /></div>
				<div class="text-xs text-gray-500">ID: {editVolume.id}</div>
			</div>
			<div class="flex justify-end gap-3 mt-6">
				<button onclick={() => { editVolume = null; }} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">취소</button>
				<button onclick={updateVolume} disabled={updating} class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg disabled:opacity-30">{updating ? '수정 중...' : '수정'}</button>
			</div>
		</div>
	</div>
{/if}

<!-- 삭제 확인 모달 -->
{#if deleteVolume}
	<div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onclick={() => { deleteVolume = null; }} role="dialog" onkeydown={(e) => e.key === 'Escape' && (deleteVolume = null)} tabindex="-1">
		<div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-sm mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()}>
			<h2 class="text-lg font-semibold text-white mb-3">볼륨 삭제</h2>
			<p class="text-sm text-gray-400 mb-2"><span class="text-white">{deleteVolume.name || deleteVolume.id.slice(0, 8)}</span> 볼륨을 삭제하시겠습니까?</p>
			<p class="text-xs text-red-400 mb-4">이 작업은 되돌릴 수 없습니다.</p>
			{#if deleteError}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{deleteError}</div>{/if}
			<div class="flex justify-end gap-3">
				<button onclick={() => { deleteVolume = null; }} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">취소</button>
				<button onclick={confirmDelete} disabled={deleting} class="px-4 py-2 bg-red-600 hover:bg-red-500 text-white text-sm font-medium rounded-lg disabled:opacity-30">{deleting ? '삭제 중...' : '삭제'}</button>
			</div>
		</div>
	</div>
{/if}

<!-- 용량 확장 모달 -->
{#if extendVolume}
	<div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onclick={() => { extendVolume = null; }} role="dialog" onkeydown={(e) => e.key === 'Escape' && (extendVolume = null)} tabindex="-1">
		<div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-sm mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()}>
			<h2 class="text-lg font-semibold text-white mb-3">용량 확장</h2>
			<p class="text-xs text-gray-500 mb-4">현재: {extendVolume.size} GB</p>
			{#if extendError}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{extendError}</div>{/if}
			<div>
				<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">새 크기 (GB)</label>
				<input bind:value={newSize} type="number" min={extendVolume.size + 1} class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
			</div>
			<div class="flex justify-end gap-3 mt-5">
				<button onclick={() => { extendVolume = null; }} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">취소</button>
				<button onclick={confirmExtend} disabled={extending || newSize <= extendVolume.size} class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg disabled:opacity-30">{extending ? '확장 중...' : '확장'}</button>
			</div>
		</div>
	</div>
{/if}

<!-- 상태 변경 모달 -->
{#if resetVolume}
	<div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onclick={() => { resetVolume = null; }} role="dialog" onkeydown={(e) => e.key === 'Escape' && (resetVolume = null)} tabindex="-1">
		<div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-sm mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()}>
			<h2 class="text-lg font-semibold text-white mb-3">상태 변경</h2>
			{#if resetError}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{resetError}</div>{/if}
			<div>
				<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">변경할 상태</label>
				<select bind:value={resetStatus} class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none">
					<option value="available">available</option>
					<option value="error">error</option>
					<option value="in-use">in-use</option>
				</select>
			</div>
			<div class="flex justify-end gap-3 mt-5">
				<button onclick={() => { resetVolume = null; }} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">취소</button>
				<button onclick={confirmReset} disabled={resetting} class="px-4 py-2 bg-yellow-600 hover:bg-yellow-500 text-white text-sm font-medium rounded-lg disabled:opacity-30">{resetting ? '변경 중...' : '변경'}</button>
			</div>
		</div>
	</div>
{/if}

<!-- 강제 삭제 모달 -->
{#if forceDeleteVolume}
	<div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
		onclick={() => { forceDeleteVolume = null; }} role="dialog"
		onkeydown={(e) => e.key === 'Escape' && (forceDeleteVolume = null)} tabindex="-1">
		<div class="bg-gray-900 border border-rose-800 rounded-xl p-6 w-full max-w-sm mx-4 shadow-2xl"
			onclick={(e) => e.stopPropagation()} role="none">
			<h2 class="text-lg font-semibold text-rose-400 mb-3">볼륨 강제 삭제</h2>
			<p class="text-sm text-gray-300 mb-2">
				<span class="text-white font-mono">{forceDeleteVolume.name || forceDeleteVolume.id.slice(0,8)}</span>
				({forceDeleteVolume.status})
			</p>
			<p class="text-xs text-rose-400 mb-1">상태 무관 강제 삭제. Cinder DB row 정리 목적이며 Ceph backend가 NotFound인 경우에만 사용하세요.</p>
			<p class="text-xs text-gray-500 mb-4">attached 볼륨은 거부됩니다.</p>
			{#if forceDeleteError}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{forceDeleteError}</div>{/if}
			<div class="flex justify-end gap-3">
				<button onclick={() => { forceDeleteVolume = null; }}
					class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">취소</button>
				<button onclick={confirmForceDelete} disabled={forceDeleting}
					class="px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white text-sm font-medium rounded-lg disabled:opacity-30">
					{forceDeleting ? '삭제 중...' : '강제 삭제'}
				</button>
			</div>
		</div>
	</div>
{/if}

<!-- 볼륨 이전 모달 -->
{#if transferVolume}
	<div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onclick={() => { transferVolume = null; }} role="dialog" onkeydown={(e) => e.key === 'Escape' && (transferVolume = null)} tabindex="-1">
		<div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()}>
			<h2 class="text-lg font-semibold text-white mb-3">볼륨 프로젝트 이전</h2>
			<p class="text-xs text-gray-500 mb-4">볼륨 <span class="text-white">{transferVolume.name || transferVolume.id.slice(0, 8)}</span>을 다른 프로젝트로 이전합니다.</p>
			{#if transferError}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{transferError}</div>{/if}
			<div class="relative">
				<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">대상 프로젝트 *</label>
				<input
					type="text"
					bind:value={transferSearch}
					onfocus={() => showTransferDropdown = true}
					oninput={() => { showTransferDropdown = true; if (!transferSearch) { transferProjectId = ''; transferProjectName = ''; } }}
					onblur={() => setTimeout(() => { showTransferDropdown = false; }, 150)}
					placeholder="프로젝트 검색..."
					class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
				/>
				{#if showTransferDropdown && filteredTransferProjects.length > 0}
					<div class="absolute z-10 w-full mt-1 bg-gray-800 border border-gray-700 rounded-lg shadow-xl max-h-40 overflow-y-auto">
						{#each filteredTransferProjects as p (p.id)}
							<button
								type="button"
								onmousedown={() => { transferProjectId = p.id; transferProjectName = p.name; transferSearch = p.name; showTransferDropdown = false; }}
								class="w-full text-left px-3 py-2 text-sm text-gray-300 hover:bg-gray-700 transition-colors {transferProjectId === p.id ? 'bg-gray-700 text-white' : ''}"
							>{p.name}</button>
						{/each}
					</div>
				{/if}
				{#if transferProjectName}
					<div class="mt-1 text-xs text-gray-500">선택됨: <span class="text-blue-400">{transferProjectName}</span></div>
				{/if}
			</div>
			<div class="flex justify-end gap-3 mt-6">
				<button onclick={() => { transferVolume = null; }} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">취소</button>
				<button onclick={confirmTransfer} disabled={transferring || !transferProjectId} class="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-sm font-medium rounded-lg disabled:opacity-30">{transferring ? '이전 중...' : '이전'}</button>
			</div>
		</div>
	</div>
{/if}

<!-- 볼륨 상세 패널 -->
{#if selectedVolumeId}
	<SlidePanel onClose={() => { selectedVolumeId = null; }} width="w-full md:w-[50vw] max-w-2xl">
		{#await import('$lib/components/AdminVolumeDetailPanel.svelte') then { default: Panel }}
			<Panel volumeId={selectedVolumeId} onClose={() => { selectedVolumeId = null; }} onRefresh={() => load(markerStack[markerStack.length - 1])} token={token} projectId={projectId} />
		{:catch}
			<!-- Fallback: 기존 상세 페이지로 이동 -->
			<div class="p-6">
				<a href="/admin/volumes/{selectedVolumeId}" class="text-blue-400 hover:text-blue-300">상세 페이지에서 보기 →</a>
			</div>
		{/await}
	</SlidePanel>
{/if}
