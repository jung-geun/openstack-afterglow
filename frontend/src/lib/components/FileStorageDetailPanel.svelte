<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import { createFileStorageDetailStore, provideFileStorageDetail } from '$lib/stores/fileStorageDetail.svelte';
	import DetailHeader from '$lib/components/ui/DetailHeader.svelte';
	import FileStorageDetailHeader from '$lib/components/file-storage/FileStorageDetailHeader.svelte';
	import FileStorageInfoSection from '$lib/components/file-storage/FileStorageInfoSection.svelte';
	import FileStorageExportLocationsSection from '$lib/components/file-storage/FileStorageExportLocationsSection.svelte';
	import FileStorageAccessRulesSection from '$lib/components/file-storage/FileStorageAccessRulesSection.svelte';
	import FileStorageMetadataSection from '$lib/components/file-storage/FileStorageMetadataSection.svelte';

	interface Props {
		fileStorageId: string;
		onClose?: () => void;
		onDeleted?: () => void;
	}

	let { fileStorageId, onClose, onDeleted }: Props = $props();

	const s = createFileStorageDetailStore({
		fileStorageId: () => fileStorageId,
		token: () => $auth.token ?? undefined,
		projectId: () => $auth.projectId ?? undefined,
		onDeleted: () => onDeleted?.(),
		onClose: () => onClose?.(),
	});
	provideFileStorageDetail(s);

	const ar = createAutoRefresh(() => s.fetchAll(), {
		storageKey: 'file-storage-detail-panel',
		defaultActive: true,
		defaultInterval: 15,
		intervalOptions: [10, 15, 30, 60],
	});

	$effect(() => {
		if (fileStorageId && $auth.token) s.fetchAll();
	});
</script>

<div class="p-6">
	<FileStorageDetailHeader {onClose} {ar} />

	{#if s.error}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">{s.error}</div>
	{:else if s.loading}
		<div class="space-y-4">
			{#each [1, 2, 3] as _}<div class="h-16 bg-gray-800 rounded-lg animate-pulse"></div>{/each}
		</div>
	{:else if s.fileStorage}
		<DetailHeader title={s.fileStorage.name || s.fileStorage.id} status={s.fileStorage.status}>
			{#snippet meta()}
				<span class="px-1.5 py-0.5 bg-purple-900/40 text-purple-300 rounded text-xs">{s.fileStorage!.share_proto}</span>
			{/snippet}
			{#snippet actions()}
				<button
					onclick={() => s.deleteFileStorage()}
					disabled={s.deleting}
					class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors"
				>
					{s.deleting ? '삭제 중...' : '삭제'}
				</button>
			{/snippet}
		</DetailHeader>

		<FileStorageInfoSection />
		{#if s.fileStorage.export_locations.length > 0}<FileStorageExportLocationsSection />{/if}
		<FileStorageAccessRulesSection />
		{#if Object.keys(s.fileStorage.metadata).length > 0}<FileStorageMetadataSection />{/if}
	{/if}
</div>
