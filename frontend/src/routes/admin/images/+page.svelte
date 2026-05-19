<script lang="ts">
	import { confirmDialog } from '$lib/stores/confirm.svelte';
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import SlidePanel from '$lib/components/SlidePanel.svelte';
	import { projectNames } from '$lib/stores/projectNames';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import AdminImagesFilters from '$lib/components/admin/images/AdminImagesFilters.svelte';
	import AdminImagesTable from '$lib/components/admin/images/AdminImagesTable.svelte';
	import ImageEditModal from '$lib/components/admin/images/ImageEditModal.svelte';
	import type { AdminImage, PagedResponse } from '$lib/types/adminImage';

	let images = $state<AdminImage[]>([]);
	let loading = $state(true), refreshing = $state(false), error = $state('');
	let searchInput = $state(''), searchFilter = $state(''), visibilityFilter = $state('');
	let pageSize = $state(20), markerStack = $state<string[]>([]), nextMarker = $state<string | null>(null);
	let selectedImageId = $state<string | null>(null);
	let editTarget = $state<AdminImage | null>(null), editForm = $state({ name: '', os_distro: '', visibility: 'private' });
	let editing = $state(false), editError = $state(''), togglingId = $state<string | null>(null);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);
	const curMarker = $derived(markerStack[markerStack.length - 1]);

	async function load(marker?: string, forceRefresh = false) {
		if (images.length === 0) loading = true; else refreshing = true;
		error = '';
		try {
			let url = `/api/admin/images?limit=${pageSize}`;
			if (marker) url += `&marker=${marker}`;
			if (searchFilter) url += `&search=${encodeURIComponent(searchFilter)}`;
			if (visibilityFilter) url += `&visibility=${encodeURIComponent(visibilityFilter)}`;
			if (forceRefresh) url += `&refresh=true`;
			const res = await api.get<PagedResponse<AdminImage>>(url, token, projectId);
			images = res.items || []; nextMarker = res.next_marker;
		} catch (e) { error = e instanceof ApiError ? e.message : '이미지 목록 조회 실패'; images = []; }
		finally { loading = false; refreshing = false; }
	}

	function openEdit(img: AdminImage) {
		editTarget = img;
		editForm = { name: img.name, os_distro: img.os_distro || '', visibility: img.visibility };
		editError = '';
	}

	async function saveEdit() {
		if (!editTarget) return;
		editing = true; editError = '';
		try {
			await api.patch(`/api/admin/images/${editTarget.id}`, {
				name: editForm.name || undefined, os_distro: editForm.os_distro || undefined, visibility: editForm.visibility || undefined,
			}, token, projectId);
			editTarget = null; await load(curMarker);
		} catch (e) { editError = e instanceof ApiError ? e.message : '수정 실패'; }
		finally { editing = false; }
	}

	async function deleteImage(img: AdminImage) {
		if (!await confirmDialog(`이미지 "${img.name}"을 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다.`)) return;
		try { await api.delete(`/api/admin/images/${img.id}`, token, projectId); await load(curMarker); }
		catch (e) { alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e))); }
	}

	async function toggleActivation(img: AdminImage) {
		togglingId = img.id;
		try {
			await api.post(`/api/admin/images/${img.id}/${img.status === 'active' ? 'deactivate' : 'reactivate'}`, {}, token, projectId);
			await load(curMarker);
		} catch (e) { alert('상태 변경 실패: ' + (e instanceof ApiError ? e.message : String(e))); }
		finally { togglingId = null; }
	}

	const ar = createAutoRefresh(() => { load(curMarker); },
		{ storageKey: 'admin-images', defaultInterval: 30, intervalOptions: [15, 30, 60] });
	async function forceRefresh() { markerStack = []; nextMarker = null; await load(undefined, true); }

	onMount(() => { load(); projectNames.load(token, projectId); });
</script>

<div class="p-4 md:p-8 max-w-7xl mx-auto">
	<PageHeader breadcrumb="COMPUTE / IMAGES" title="이미지">
		{#snippet actions()}
			<AutoRefreshControl bind:active={ar.active} bind:intervalSeconds={ar.intervalSeconds}
				intervalOptions={ar.intervalOptions} refreshing={refreshing} onManualRefresh={forceRefresh} />
			<div class="flex items-center gap-1 text-xs text-gray-500">
				표시:
				{#each [10, 20, 30] as n}
					<button onclick={() => { pageSize = n; markerStack = []; nextMarker = null; load(); }}
						class="px-2 py-0.5 rounded {pageSize === n ? 'bg-blue-600 text-white' : 'bg-gray-800 hover:bg-gray-700 text-gray-400'}"
					>{n}</button>
				{/each}
			</div>
		{/snippet}
	</PageHeader>

	<AdminImagesFilters bind:searchInput bind:visibilityFilter
		onSearchChange={(v) => { searchFilter = v; markerStack = []; nextMarker = null; load(); }}
		onVisibilityChange={() => { markerStack = []; nextMarker = null; load(); }}
	/>

	{#if error}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>
	{/if}

	{#if loading}
		<LoadingSkeleton variant="table" rows={8} />
	{:else if images.length === 0}
		<div class="text-gray-600 text-sm">이미지가 없습니다</div>
	{:else}
		<AdminImagesTable {images} {selectedImageId} {togglingId} {markerStack} {nextMarker}
			onOpenDetail={(img) => { selectedImageId = img.id; }}
			onEdit={openEdit} onToggleActivation={toggleActivation} onDelete={deleteImage}
			onPrev={() => { const prev = markerStack.slice(0,-1); markerStack = prev; load(prev[prev.length-1]); }}
			onNext={() => { if (!nextMarker) return; markerStack = [...markerStack, nextMarker]; load(nextMarker); }}
		/>
	{/if}
</div>

{#if selectedImageId}
	<SlidePanel onClose={() => { selectedImageId = null; }} width="w-full md:w-[50vw] max-w-2xl">
		{#await import('$lib/components/ImageDetailPanel.svelte') then { default: Panel }}
			<Panel imageId={selectedImageId} onClose={() => { selectedImageId = null; }} isAdmin={true} />
		{/await}
	</SlidePanel>
{/if}

<ImageEditModal bind:target={editTarget} bind:form={editForm} {editing} {editError} onSave={saveEdit} />
