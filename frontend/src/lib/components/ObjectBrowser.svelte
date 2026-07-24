<script lang="ts">
	import { createObjectBrowserStore, provideObjectBrowser } from '$lib/stores/objectBrowser.svelte';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import UploadModal from '$lib/components/UploadModal.svelte';
	import ObjectDragOverlay from '$lib/components/object-storage/ObjectDragOverlay.svelte';
	import ObjectBrowserHeader from '$lib/components/object-storage/ObjectBrowserHeader.svelte';
	import ObjectBrowserToolbar from '$lib/components/object-storage/ObjectBrowserToolbar.svelte';
	import ObjectBulkActionBar from '$lib/components/object-storage/ObjectBulkActionBar.svelte';
	import ObjectFlatTable from '$lib/components/object-storage/ObjectFlatTable.svelte';
	import ObjectTreeTable from '$lib/components/object-storage/ObjectTreeTable.svelte';
	import ObjectMetaPanel from '$lib/components/object-storage/ObjectMetaPanel.svelte';
	import ObjectTrashView from '$lib/components/object-storage/ObjectTrashView.svelte';
	import NewDirModal from '$lib/components/object-storage/NewDirModal.svelte';
	import RenameModal from '$lib/components/object-storage/RenameModal.svelte';
	import MoveModal from '$lib/components/object-storage/MoveModal.svelte';

	interface Props {
		mode: 'user' | 'admin';
		containerName: string;
		token: string | undefined;
		projectId: string | undefined;
	}

	let { mode, containerName, token, projectId }: Props = $props();

	let showTrash = $state(false);

	const s = createObjectBrowserStore({
		mode: () => mode,
		containerName: () => containerName,
		token: () => token,
		projectId: () => projectId,
	});
	provideObjectBrowser(s);

	const storageKey = mode === 'user' ? 'object-browser-user' : 'object-browser-admin';

	const ar = createAutoRefresh(
		() => {
			if (s.loading) return;
			return mode === 'user' ? s.refreshAll({ silent: true }) : s.load({ silent: true });
		},
		{ storageKey, defaultActive: true, defaultInterval: 15, intervalOptions: [10, 15, 30, 60], invokeOnMount: false }
	);

	const onManualRefresh = mode === 'user'
		? () => { s.refreshAll(); s.loadContainerMeta(); }
		: () => s.load();

	const onUploadSuccess = mode === 'user'
		? () => s.refreshAll({ silent: true })
		: () => s.load({ silent: true });

	function hasFiles(e: DragEvent): boolean {
		const types = e.dataTransfer?.types;
		if (!types) return false;
		for (let i = 0; i < types.length; i++) if (types[i] === 'Files') return true;
		return false;
	}

	function onWindowDragEnter(e: DragEvent) {
		if (!hasFiles(e)) return;
		e.preventDefault();
		s.dragActive = true;
	}
	function onWindowDragOver(e: DragEvent) {
		if (!hasFiles(e)) return;
		e.preventDefault();
		s.dragActive = true;
	}
	function onWindowDragLeave(e: DragEvent) {
		if (!hasFiles(e)) return;
		if (e.clientX <= 0 || e.clientY <= 0 || e.clientX >= window.innerWidth || e.clientY >= window.innerHeight) {
			s.dragActive = false;
		}
	}
	function onWindowDrop(e: DragEvent) {
		if (!hasFiles(e)) return;
		e.preventDefault();
		s.dragActive = false;
		s.handleDrop(e);
	}
</script>

<svelte:window
	ondragenter={onWindowDragEnter}
	ondragover={onWindowDragOver}
	ondragleave={onWindowDragLeave}
	ondrop={onWindowDrop}
/>

<ObjectDragOverlay />

<div class:bulk-selection-page={mode === 'user'} class="p-4 md:p-8 max-w-7xl mx-auto">
	<ObjectBrowserHeader />

	<!-- 탭 전환: 파일 목록 / 휴지통 -->
	<div class="flex items-center gap-2 mb-3">
		<button
			onclick={() => { showTrash = false; s.selected = new Set(); }}
			class="text-xs px-3 py-1 rounded transition-colors {!showTrash ? 'bg-indigo-700 text-white' : 'text-gray-400 hover:text-gray-200 border border-gray-700'}"
		>파일</button>
		<button
			onclick={() => { showTrash = true; s.selected = new Set(); }}
			class="text-xs px-3 py-1 rounded transition-colors {showTrash ? 'bg-orange-800 text-orange-200' : 'text-gray-400 hover:text-gray-200 border border-gray-700'}"
		>🗑 휴지통</button>
	</div>

	{#if showTrash}
		<ObjectTrashView {containerName} {token} {projectId} selectionEnabled={mode === 'user'} />
	{:else}
		<ObjectBrowserToolbar {ar} {onManualRefresh} />
		<ObjectBulkActionBar {mode} />

		{#if s.showUpload}
			<UploadModal
				{containerName}
				prefix={s.prefix}
				{token}
				{projectId}
				onSuccess={onUploadSuccess}
				onClose={() => { s.showUpload = false; }}
			/>
		{/if}

		<NewDirModal />
		<RenameModal />
		<MoveModal />
		<MoveModal bulk />

		<div class="flex gap-6">
			<div class="flex-1 min-w-0 relative">
				{#if mode === 'user'}
					<ObjectTreeTable />
				{:else}
					<ObjectFlatTable />
				{/if}
			</div>
			<ObjectMetaPanel />
		</div>
	{/if}
</div>
