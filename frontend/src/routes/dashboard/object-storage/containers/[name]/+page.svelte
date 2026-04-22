<script lang="ts">
	import { page } from '$app/stores';
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError, getBaseUrl } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
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
	let prefix = $state('');
	let deleting = $state<string | null>(null);
	let downloading = $state<string | null>(null);

	// 업로드 모달
	let showUpload = $state(false);
	let uploadFile = $state<File | null>(null);
	let uploading = $state(false);
	let uploadError = $state('');

	// 오브젝트 상세 (SlidePanel 대신 inline)
	let selectedMeta = $state<ObjectMeta | null>(null);
	let loadingMeta = $state(false);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function load() {
		loading = true;
		try {
			objects = await api.get<ObjectItem[]>(
				`/api/object-storage/${encodeURIComponent(containerName)}/objects${prefix ? `?prefix=${encodeURIComponent(prefix)}` : ''}`,
				token,
				projectId
			);
		} catch {
			objects = [];
		} finally {
			loading = false;
		}
	}

	async function upload() {
		if (!uploadFile) return;
		uploading = true;
		uploadError = '';
		try {
			const formData = new FormData();
			formData.append('file', uploadFile);
			await api.upload(`/api/object-storage/${encodeURIComponent(containerName)}/objects`, formData, token, projectId);
			showUpload = false;
			uploadFile = null;
			await load();
		} catch (e) {
			uploadError = e instanceof ApiError ? e.message : '업로드 실패';
		} finally {
			uploading = false;
		}
	}

	async function downloadObject(name: string) {
		downloading = name;
		try {
			const { blob, filename } = await api.downloadBlob(
				`/api/object-storage/${encodeURIComponent(containerName)}/objects/${name.split('/').map(encodeURIComponent).join('/')}/download`,
				token,
				projectId
			);
			const url = URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = url;
			a.download = filename;
			a.click();
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
				`/api/object-storage/${encodeURIComponent(containerName)}/objects/${name.split('/').map(encodeURIComponent).join('/')}`	,
				token,
				projectId
			);
			await load();
		} catch (e) {
			alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			deleting = null;
		}
	}

	async function showMeta(name: string) {
		loadingMeta = true;
		selectedMeta = null;
		try {
			selectedMeta = await api.get<ObjectMeta>(
				`/api/object-storage/${encodeURIComponent(containerName)}/objects/${name.split('/').map(encodeURIComponent).join('/')}/metadata`,
				token,
				projectId
			);
		} catch {
			// ignore
		} finally {
			loadingMeta = false;
		}
	}

	onMount(load);
</script>

<div class="p-4 md:p-8 max-w-6xl">
	<!-- 헤더 -->
	<div class="flex items-center gap-2 mb-2">
		<a href="/dashboard/object-storage/containers" class="text-gray-500 hover:text-gray-300 text-sm">Object Storage</a>
		<span class="text-gray-700">/</span>
		<span class="text-white text-sm font-medium">{containerName}</span>
	</div>

	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-white">{containerName}</h1>
		<div class="flex gap-2">
			<button
				onclick={() => { showUpload = true; uploadError = ''; uploadFile = null; }}
				class="text-xs text-white bg-indigo-600 hover:bg-indigo-500 transition-colors px-3 py-1.5 rounded border border-indigo-500"
			>+ 업로드</button>
			<button onclick={load} class="text-xs text-gray-400 hover:text-white transition-colors px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600">새로고침</button>
		</div>
	</div>

	<!-- 업로드 모달 -->
	{#if showUpload}
		<div
			class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
			onclick={() => { showUpload = false; }}
			role="dialog"
			aria-modal="true"
			tabindex="-1"
			onkeydown={(e) => e.key === 'Escape' && (showUpload = false)}
		>
			<div
				class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl"
				onclick={(e) => e.stopPropagation()}
				role="none"
				onkeydown={(e) => e.stopPropagation()}
			>
				<h2 class="text-lg font-semibold text-white mb-4">파일 업로드</h2>
				<div class="space-y-3">
					<input
						type="file"
						onchange={(e) => { uploadFile = (e.target as HTMLInputElement).files?.[0] ?? null; }}
						class="w-full text-sm text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:bg-gray-700 file:text-white hover:file:bg-gray-600"
					/>
					{#if uploadError}
						<p class="text-red-400 text-xs">{uploadError}</p>
					{/if}
				</div>
				<div class="flex justify-end gap-2 mt-5">
					<button
						onclick={() => { showUpload = false; }}
						class="px-4 py-2 text-sm text-gray-400 hover:text-white border border-gray-700 rounded-lg transition-colors"
					>취소</button>
					<button
						onclick={upload}
						disabled={uploading || !uploadFile}
						class="px-4 py-2 text-sm bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded-lg transition-colors"
					>{uploading ? '업로드 중...' : '업로드'}</button>
				</div>
			</div>
		</div>
	{/if}

	<div class="flex gap-6">
		<!-- 오브젝트 목록 -->
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
										<button
											onclick={() => showMeta(obj.name)}
											class="text-indigo-400 hover:text-indigo-300 text-left truncate max-w-xs"
										>{obj.name}</button>
									</td>
									<td class="py-3 px-4 text-gray-300 whitespace-nowrap">
										{obj.bytes >= 1073741824
											? formatStorage(Math.round(obj.bytes / 1073741824))
											: obj.bytes >= 1048576
											? `${(obj.bytes / 1048576).toFixed(1)} MB`
											: `${Math.round(obj.bytes / 1024)} KB`}
									</td>
									<td class="py-3 px-4 text-gray-500 text-xs">{obj.content_type || '-'}</td>
									<td class="py-3 px-4 text-right flex justify-end gap-1">
										<button
											onclick={() => downloadObject(obj.name)}
											disabled={downloading === obj.name}
											class="text-blue-400 hover:text-blue-300 disabled:text-gray-600 text-xs px-2 py-1 rounded border border-blue-900 hover:border-blue-700 disabled:border-gray-700 transition-colors"
										>{downloading === obj.name ? '...' : '다운로드'}</button>
										<button
											onclick={(e) => { e.stopPropagation(); deleteObject(obj.name); }}
											disabled={deleting === obj.name}
											class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-1 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors"
										>{deleting === obj.name ? '...' : '삭제'}</button>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</div>

		<!-- 오브젝트 메타데이터 패널 -->
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
					<div>
						<div class="text-gray-500 text-xs">이름</div>
						<div class="text-white break-all">{selectedMeta.name}</div>
					</div>
					<div>
						<div class="text-gray-500 text-xs">크기</div>
						<div class="text-white">{selectedMeta.bytes.toLocaleString()} bytes</div>
					</div>
					<div>
						<div class="text-gray-500 text-xs">Content-Type</div>
						<div class="text-white">{selectedMeta.content_type || '-'}</div>
					</div>
					<div>
						<div class="text-gray-500 text-xs">ETag (MD5)</div>
						<div class="text-gray-400 font-mono text-xs break-all">{selectedMeta.etag || '-'}</div>
					</div>
					<div>
						<div class="text-gray-500 text-xs">수정일</div>
						<div class="text-white">{selectedMeta.last_modified ? selectedMeta.last_modified.slice(0, 19) : '-'}</div>
					</div>
					{#if selectedMeta.content_encoding}
						<div>
							<div class="text-gray-500 text-xs">Content-Encoding</div>
							<div class="text-white">{selectedMeta.content_encoding}</div>
						</div>
					{/if}
				</div>
			</div>
		{/if}
	</div>
</div>
