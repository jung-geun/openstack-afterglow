<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import SlidePanel from '$lib/components/SlidePanel.svelte';
	import { projectNames } from '$lib/stores/projectNames';

	interface AdminImage {
		id: string;
		name: string;
		status: string;
		size: number;
		min_disk: number;
		min_ram: number;
		disk_format: string;
		os_distro: string | null;
		visibility: string;
		owner: string;
		created_at: string | null;
		protected: boolean;
	}
	interface PagedResponse<T> {
		items: T[];
		next_marker: string | null;
		count: number;
	}

	const visibilityColor: Record<string, string> = {
		public:    'text-green-400 bg-green-900/30',
		community: 'text-blue-400 bg-blue-900/30',
		shared:    'text-yellow-400 bg-yellow-900/30',
		private:   'text-gray-400 bg-gray-800',
	};

	let images = $state<AdminImage[]>([]);
	let loading = $state(true);
	let error = $state('');
	let searchInput = $state('');
	let searchFilter = $state('');
	let visibilityFilter = $state('');
	let pageSize = $state(20);
	let markerStack = $state<string[]>([]);
	let nextMarker = $state<string | null>(null);

	// 상세 패널
	let selectedImageId = $state<string | null>(null);

	// 수정 모달
	let editTarget = $state<AdminImage | null>(null);
	let editForm = $state({ name: '', os_distro: '', visibility: 'private' });
	let editing = $state(false);
	let editError = $state('');

	// activate/deactivate 상태
	let togglingId = $state<string | null>(null);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	let searchTimeout: ReturnType<typeof setTimeout>;
	function onSearchInput() {
		clearTimeout(searchTimeout);
		searchTimeout = setTimeout(() => {
			searchFilter = searchInput;
			markerStack = [];
			nextMarker = null;
			load();
		}, 400);
	}

	function formatSize(bytes: number): string {
		if (!bytes) return '-';
		if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(1)} GB`;
		if (bytes >= 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(0)} MB`;
		return `${bytes} B`;
	}

	async function load(marker?: string) {
		loading = true;
		error = '';
		try {
			let url = `/api/admin/images?limit=${pageSize}`;
			if (marker) url += `&marker=${marker}`;
			if (searchFilter) url += `&search=${encodeURIComponent(searchFilter)}`;
			const res = await api.get<PagedResponse<AdminImage>>(url, token, projectId);
			images = (res.items || []).filter(img => !visibilityFilter || img.visibility === visibilityFilter);
			nextMarker = res.next_marker;
		} catch (e) {
			error = e instanceof ApiError ? e.message : '이미지 목록 조회 실패';
			images = [];
		} finally {
			loading = false;
		}
	}

	function openEdit(img: AdminImage) {
		editTarget = img;
		editForm = { name: img.name, os_distro: img.os_distro || '', visibility: img.visibility };
		editError = '';
	}

	async function saveEdit() {
		if (!editTarget) return;
		editing = true;
		editError = '';
		try {
			await api.patch(`/api/admin/images/${editTarget.id}`, {
				name: editForm.name || undefined,
				os_distro: editForm.os_distro || undefined,
				visibility: editForm.visibility || undefined,
			}, token, projectId);
			editTarget = null;
			await load(markerStack[markerStack.length - 1]);
		} catch (e) {
			editError = e instanceof ApiError ? e.message : '수정 실패';
		} finally {
			editing = false;
		}
	}

	async function deleteImage(img: AdminImage) {
		if (!confirm(`이미지 "${img.name}"을 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다.`)) return;
		try {
			await api.delete(`/api/admin/images/${img.id}`, token, projectId);
			await load(markerStack[markerStack.length - 1]);
		} catch (e) {
			alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		}
	}

	async function toggleActivation(img: AdminImage) {
		togglingId = img.id;
		try {
			const action = img.status === 'active' ? 'deactivate' : 'reactivate';
			await api.post(`/api/admin/images/${img.id}/${action}`, {}, token, projectId);
			await load(markerStack[markerStack.length - 1]);
		} catch (e) {
			alert('상태 변경 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			togglingId = null;
		}
	}

	function openDetail(img: AdminImage) {
		selectedImageId = img.id;
	}

	function closeDetail() {
		selectedImageId = null;
	}

	onMount(() => {
		load();
		projectNames.load(token, projectId);
	});
</script>

<div class="p-4 md:p-8 max-w-7xl">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-white">이미지 관리</h1>
		<div class="flex items-center gap-3">
			<button onclick={() => { markerStack = []; nextMarker = null; load(); }} class="text-xs text-gray-400 hover:text-white transition-colors px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600">새로고침</button>
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
			bind:value={searchInput}
			oninput={onSearchInput}
			class="bg-gray-800 border border-gray-700 text-sm text-gray-300 rounded-lg px-3 py-1.5 w-48 focus:outline-none focus:border-blue-500"
		/>
		<select bind:value={visibilityFilter} onchange={() => { markerStack = []; nextMarker = null; load(); }} class="bg-gray-800 border border-gray-700 text-sm text-gray-300 rounded-lg px-3 py-1.5 focus:outline-none focus:border-blue-500">
			<option value="">공개 범위 전체</option>
			<option value="public">Public</option>
			<option value="community">Community</option>
			<option value="shared">Shared</option>
			<option value="private">Private</option>
		</select>
	</div>

	{#if error}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>
	{/if}

	{#if loading}
		<LoadingSkeleton variant="table" rows={8} />
	{:else if images.length === 0}
		<div class="text-gray-600 text-sm">이미지가 없습니다</div>
	{:else}
		<div class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
						<th class="text-left py-2 pr-4">이름</th>
						<th class="text-left py-2 pr-4">상태</th>
						<th class="text-left py-2 pr-4">공개 범위</th>
						<th class="text-left py-2 pr-4">크기</th>
						<th class="text-left py-2 pr-4">포맷</th>
						<th class="text-left py-2 pr-4">프로젝트</th>
						<th class="text-left py-2 pr-4">생성일</th>
						<th class="text-right py-2">액션</th>
					</tr>
				</thead>
				<tbody>
					{#each images as img (img.id)}
						<tr
							onclick={() => openDetail(img)}
							class="border-b border-gray-800/50 text-xs hover:bg-gray-800/30 transition-colors cursor-pointer {selectedImageId === img.id ? 'bg-gray-800/50' : ''}"
						>
							<td class="py-2 pr-4">
								<div>
									<span class="text-white">{img.name || img.id.slice(0, 12)}</span>
									{#if img.os_distro}
										<div class="text-gray-500 text-xs mt-0.5">{img.os_distro}</div>
									{/if}
								</div>
							</td>
							<td class="py-2 pr-4">
								<span class="{img.status === 'active' ? 'text-green-400' : img.status === 'deactivated' ? 'text-orange-400' : img.status === 'queued' ? 'text-yellow-400' : 'text-red-400'}">{img.status}</span>
							</td>
							<td class="py-2 pr-4">
								<span class="px-1.5 py-0.5 rounded text-xs {visibilityColor[img.visibility] ?? 'text-gray-400 bg-gray-800'}">{img.visibility}</span>
							</td>
							<td class="py-2 pr-4 text-gray-400">{formatSize(img.size)}</td>
							<td class="py-2 pr-4 text-gray-400">{img.disk_format || '-'}</td>
							<td class="py-2 pr-4 text-gray-400">
								{img.owner ? ($projectNames.get(img.owner) ?? img.owner.slice(0, 8)) : '-'}
							</td>
							<td class="py-2 pr-4 text-gray-500">{img.created_at ? img.created_at.slice(0, 10) : '-'}</td>
							<td class="py-2 text-right" onclick={(e) => e.stopPropagation()}>
								<div class="flex items-center justify-end gap-2">
									{#if img.status === 'active' || img.status === 'deactivated'}
										<button
											onclick={() => toggleActivation(img)}
											disabled={togglingId === img.id}
											class="text-xs {img.status === 'active' ? 'text-orange-400 hover:text-orange-300' : 'text-green-400 hover:text-green-300'} disabled:opacity-40"
										>
											{togglingId === img.id ? '...' : img.status === 'active' ? '비활성화' : '활성화'}
										</button>
									{/if}
									<button onclick={() => openEdit(img)} class="text-blue-400 hover:text-blue-300 text-xs">수정</button>
									{#if !img.protected}
										<button onclick={() => deleteImage(img)} class="text-red-400 hover:text-red-300 text-xs">삭제</button>
									{/if}
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

<!-- 우측 상세 패널 -->
{#if selectedImageId}
	<SlidePanel onClose={closeDetail} width="w-full md:w-[50vw] max-w-2xl">
		{#await import('$lib/components/ImageDetailPanel.svelte') then { default: Panel }}
			<Panel imageId={selectedImageId} onClose={closeDetail} />
		{/await}
	</SlidePanel>
{/if}

<!-- 수정 모달 -->
{#if editTarget}
	<div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onclick={() => { editTarget = null; }} role="dialog" onkeydown={(e) => e.key === 'Escape' && (editTarget = null)} tabindex="-1">
		<div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()}>
			<h2 class="text-lg font-semibold text-white mb-5">이미지 수정</h2>
			{#if editError}
				<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{editError}</div>
			{/if}
			<div class="space-y-4">
				<div>
					<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름</label>
					<input bind:value={editForm.name} type="text" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
				</div>
				<div>
					<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">OS 배포판</label>
					<input bind:value={editForm.os_distro} type="text" placeholder="ubuntu, centos, rocky ..." class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
				</div>
				<div>
					<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">공개 범위</label>
					<select bind:value={editForm.visibility} class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500">
						<option value="public">public</option>
						<option value="community">community</option>
						<option value="shared">shared</option>
						<option value="private">private</option>
					</select>
				</div>
			</div>
			<div class="flex justify-end gap-3 mt-6">
				<button onclick={() => { editTarget = null; }} class="px-4 py-2 text-sm text-gray-400 hover:text-white">취소</button>
				<button onclick={saveEdit} disabled={editing} class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg disabled:opacity-30">
					{editing ? '저장 중...' : '저장'}
				</button>
			</div>
		</div>
	</div>
{/if}
