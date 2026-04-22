<script lang="ts">
	import { page } from '$app/stores';
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import UploadModal from '$lib/components/UploadModal.svelte';
	import { formatStorage } from '$lib/utils/format';

	interface ObjectItem {
		name: string;
		bytes: number;
		content_type: string;
		last_modified: string;
		etag: string;
	}

	interface ObjectMeta extends ObjectItem {
		container: string;
		content_encoding: string;
		content_disposition: string;
		delete_at: string;
	}

	const containerName = $derived(decodeURIComponent($page.params.name ?? ''));
	let objects = $state<ObjectItem[]>([]);
	let loading = $state(true);
	let deleting = $state<string | null>(null);
	let downloading = $state<string | null>(null);

	let showUpload = $state(false);

	let selectedMeta = $state<ObjectMeta | null>(null);
	let loadingMeta = $state(false);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function load() {
		loading = true;
		try {
			objects = await api.get<ObjectItem[]>(
				`/api/object-storage/${encodeURIComponent(containerName)}/objects`,
				token, projectId
			);
		} catch {
			objects = [];
		} finally {
			loading = false;
		}
	}

	async function downloadObject(name: string) {
		downloading = name;
		try {
			const { blob, filename } = await api.downloadBlob(
				`/api/object-storage/${encodeURIComponent(containerName)}/objects/${name.split('/').map(encodeURIComponent).join('/')}/download`,
				token, projectId
			);
			const url = URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = url; a.download = filename; a.click();
			URL.revokeObjectURL(url);
		} catch (e) {
			alert('다운로드 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			downloading = null;
		}
	}

	async function deleteObject(name: string) {
		if (!confirm(`"${name}" 오브젝트를 삭제하시겠습니까?`)) return;
		deleting = name;
		try {
			await api.delete(
				`/api/object-storage/${encodeURIComponent(containerName)}/objects/${name.split('/').map(encodeURIComponent).join('/')}`,
				token, projectId
			);
			await load();
		} catch (e) {
			alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			deleting = null;
		}
	}

	async function showMeta(name: string) {
		loadingMeta = true; selectedMeta = null;
		try {
			selectedMeta = await api.get<ObjectMeta>(
				`/api/object-storage/${encodeURIComponent(containerName)}/objects/${name.split('/').map(encodeURIComponent).join('/')}/metadata`,
				token, projectId
			);
		} catch { /* ignore */ }
		finally { loadingMeta = false; }
	}

	onMount(load);
</script>

<div class="p-4 md:p-8 max-w-6xl">
	<div class="flex items-center gap-2 mb-2">
		<a href="/admin/object-storage" class="text-gray-500 hover:text-gray-300 text-sm">Object Storage</a>
		<span class="text-gray-700">/</span>
		<span class="text-white text-sm font-medium">{containerName}</span>
	</div>

	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-white">{containerName}</h1>
		<div class="flex gap-2">
			<button onclick={() => { showUpload = true; }}
				class="text-xs text-white bg-indigo-600 hover:bg-indigo-500 transition-colors px-3 py-1.5 rounded border border-indigo-500">+ 업로드</button>
			<button onclick={load} class="text-xs text-gray-400 hover:text-white transition-colors px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600">새로고침</button>
		</div>
	</div>

	{#if showUpload}
		<UploadModal
			{containerName}
			{token}
			{projectId}
			onSuccess={load}
			onClose={() => { showUpload = false; }}
		/>
	{/if}

	<div class="flex gap-6">
		<div class="flex-1 min-w-0">
			{#if loading}
				<LoadingSkeleton variant="table" rows={5} />
			{:else if objects.length === 0}
				<div class="text-gray-600 text-sm">오브젝트가 없습니다</div>
			{:else}
				<div class="overflow-x-auto">
					<table class="w-full text-sm">
						<thead>
							<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
								<th class="text-left py-3 px-4 font-medium">이름</th>
								<th class="text-left py-3 px-4 font-medium">크기</th>
								<th class="text-left py-3 px-4 font-medium">타입</th>
								<th class="text-right py-3 px-4 font-medium">액션</th>
							</tr>
						</thead>
						<tbody>
							{#each objects as obj}
								<tr class="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
									<td class="py-3 px-4">
										<button onclick={() => showMeta(obj.name)}
											class="text-indigo-400 hover:text-indigo-300 text-left truncate max-w-xs">{obj.name}</button>
									</td>
									<td class="py-3 px-4 text-gray-300 whitespace-nowrap">
										{obj.bytes >= 1073741824 ? formatStorage(Math.round(obj.bytes / 1073741824))
											: obj.bytes >= 1048576 ? `${(obj.bytes / 1048576).toFixed(1)} MB`
											: `${Math.round(obj.bytes / 1024)} KB`}
									</td>
									<td class="py-3 px-4 text-gray-500 text-xs">{obj.content_type || '-'}</td>
									<td class="py-3 px-4 text-right">
										<div class="flex justify-end gap-1">
											<button onclick={() => downloadObject(obj.name)} disabled={downloading === obj.name}
												class="text-blue-400 hover:text-blue-300 disabled:text-gray-600 text-xs px-2 py-1 rounded border border-blue-900 hover:border-blue-700 disabled:border-gray-700 transition-colors">
												{downloading === obj.name ? '...' : '다운로드'}
											</button>
											<button onclick={(e) => { e.stopPropagation(); deleteObject(obj.name); }} disabled={deleting === obj.name}
												class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-1 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors">
												{deleting === obj.name ? '...' : '삭제'}
											</button>
										</div>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</div>

		{#if loadingMeta}
			<div class="w-72 shrink-0 bg-gray-900 border border-gray-800 rounded-xl p-4">
				<LoadingSkeleton variant="detail" rows={6} />
			</div>
		{:else if selectedMeta}
			<div class="w-72 shrink-0 bg-gray-900 border border-gray-800 rounded-xl p-4 text-sm">
				<div class="flex items-center justify-between mb-3">
					<h3 class="text-white font-medium text-xs">오브젝트 정보</h3>
					<button onclick={() => selectedMeta = null} class="text-gray-600 hover:text-gray-400 text-xs">✕</button>
				</div>
				<div class="space-y-2">
					<div><div class="text-gray-500 text-xs">이름</div><div class="text-white break-all">{selectedMeta.name}</div></div>
					<div><div class="text-gray-500 text-xs">크기</div><div class="text-white">{selectedMeta.bytes.toLocaleString()} bytes</div></div>
					<div><div class="text-gray-500 text-xs">Content-Type</div><div class="text-white">{selectedMeta.content_type || '-'}</div></div>
					<div><div class="text-gray-500 text-xs">ETag (MD5)</div><div class="text-gray-400 font-mono text-xs break-all">{selectedMeta.etag || '-'}</div></div>
					<div><div class="text-gray-500 text-xs">수정일</div><div class="text-white">{selectedMeta.last_modified ? selectedMeta.last_modified.slice(0, 19) : '-'}</div></div>
				</div>
			</div>
		{/if}
	</div>
</div>
