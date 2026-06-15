<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import { useInstanceDetailController } from '$lib/stores/instanceDetailController.svelte';
	import { get } from 'svelte/store';
	import { toast } from '$lib/stores/toast';

	const s = useInstanceDetailController();

	interface StorageAttachment {
		file_storage_id: string;
		name: string | null;
		share_proto: string | null;
		status: string;
	}

	interface FileStorage {
		id: string;
		name: string;
		status: string;
		share_proto: string;
	}

	let attachments = $state<StorageAttachment[]>([]);
	let fileStorages = $state<FileStorage[]>([]);
	let loading = $state(false);
	let showForm = $state(false);
	let selectedStorageId = $state('');
	let mountPoint = $state('');
	let readOnly = $state(false);
	let attaching = $state(false);
	let detaching = $state<string | null>(null);
	let lastMountInfo = $state<{ mount_command: string; keyring_file: string | null } | null>(null);
	let copied = $state(false);

	function tok() { return get(auth).token ?? undefined; }
	function pid() { return get(auth).projectId ?? undefined; }

	async function loadAttachments() {
		if (!s.instance) return;
		loading = true;
		try {
			attachments = await api.get<StorageAttachment[]>(
				`/api/instances/${s.instance.id}/storage-attachments`,
				tok(), pid()
			);
		} catch {
			attachments = [];
		} finally {
			loading = false;
		}
	}

	async function loadFileStorages() {
		try {
			fileStorages = await api.get<FileStorage[]>('/api/storage/file-storages', tok(), pid());
		} catch {
			fileStorages = [];
		}
	}

	async function handleAttach() {
		if (!s.instance || !selectedStorageId || !mountPoint.trim()) return;
		attaching = true;
		lastMountInfo = null;
		try {
			const result = await api.post<{ mount_command: string; keyring_file: string | null }>(
				`/api/instances/${s.instance.id}/storage-attachments`,
				{ file_storage_id: selectedStorageId, mount_point: mountPoint.trim(), read_only: readOnly },
				tok(), pid()
			);
			lastMountInfo = result;
			showForm = false;
			selectedStorageId = '';
			mountPoint = '';
			readOnly = false;
			await loadAttachments();
		} catch (e) {
			toast.error('연결 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			attaching = false;
		}
	}

	async function handleDetach(fileStorageId: string) {
		if (!s.instance) return;
		detaching = fileStorageId;
		try {
			await api.delete(
				`/api/instances/${s.instance.id}/storage-attachments/${fileStorageId}`,
				tok(), pid()
			);
			await loadAttachments();
			if (lastMountInfo) lastMountInfo = null;
		} catch (e) {
			toast.error('연결 해제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			detaching = null;
		}
	}

	async function copyToClipboard(text: string) {
		try {
			await navigator.clipboard.writeText(text);
			copied = true;
			setTimeout(() => { copied = false; }, 2000);
		} catch {
			// ignore
		}
	}

	$effect(() => {
		if (s.instance) {
			void loadAttachments();
			void loadFileStorages();
		}
	});

	const availableStorages = $derived(
		fileStorages.filter(f => f.status === 'available' && !attachments.some(a => a.file_storage_id === f.id))
	);
</script>

<div class="bg-gray-900 border border-gray-800 rounded-lg p-6 mb-4">
	<div class="flex items-center justify-between mb-4">
		<h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide">파일 스토리지</h2>
		<button
			onclick={() => { showForm = !showForm; selectedStorageId = ''; mountPoint = ''; readOnly = false; }}
			class="text-xs text-blue-400 hover:text-blue-300 transition-colors"
		>
			{showForm ? '닫기' : '+ 연결'}
		</button>
	</div>

	{#if showForm}
		<div class="mb-4 bg-gray-800 rounded-lg p-4">
			<div class="grid grid-cols-1 gap-3 mb-3">
				<div>
					<label class="block text-xs text-gray-400 mb-1">파일 스토리지</label>
					<select
						bind:value={selectedStorageId}
						class="w-full bg-gray-700 border border-gray-600 text-white text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500"
					>
						<option value="">선택...</option>
						{#each availableStorages as fs}
							<option value={fs.id}>{fs.name || fs.id.slice(0, 12)} ({fs.share_proto})</option>
						{/each}
					</select>
					{#if availableStorages.length === 0}
						<p class="text-xs text-amber-400 mt-1">연결 가능한 파일 스토리지가 없습니다.</p>
					{/if}
				</div>
				<div>
					<label class="block text-xs text-gray-400 mb-1">마운트 경로</label>
					<input
						type="text"
						bind:value={mountPoint}
						placeholder="/mnt/mydata"
						class="w-full bg-gray-700 border border-gray-600 text-white text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500"
					/>
					<p class="text-[10.5px] text-gray-600 mt-0.5">/mnt, /data, /srv, /home 하위 경로만 허용</p>
				</div>
				<label class="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
					<input
						type="checkbox"
						bind:checked={readOnly}
						class="w-4 h-4 rounded border-gray-600 bg-gray-800 text-blue-500"
					/>
					읽기 전용으로 마운트
				</label>
			</div>
			<button
				onclick={handleAttach}
				disabled={attaching || !selectedStorageId || !mountPoint.trim()}
				class="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm rounded-lg transition-colors"
			>
				{attaching ? '연결 중...' : '연결'}
			</button>
		</div>
	{/if}

	{#if lastMountInfo}
		<div class="mb-4 bg-green-900/20 border border-green-700/50 rounded-lg p-4">
			<p class="text-xs text-green-400 font-medium mb-2">연결 완료 — VM 내부에서 아래 명령을 실행하세요</p>
			{#if lastMountInfo.keyring_file}
				<p class="text-[10.5px] text-gray-400 mb-1.5">
					키링 파일이 cloud-init으로 미리 주입된 경우 <code class="text-gray-300">{lastMountInfo.keyring_file}</code>에 존재합니다.
					런타임 연결 시 키링 파일을 직접 생성해야 할 수 있습니다.
				</p>
			{/if}
			<div class="flex items-center gap-2">
				<code class="flex-1 text-xs font-mono bg-gray-900 text-cyan-300 px-3 py-2 rounded break-all">{lastMountInfo.mount_command}</code>
				<button
					onclick={() => copyToClipboard(lastMountInfo!.mount_command)}
					class="shrink-0 px-2 py-1.5 text-xs {copied ? 'text-green-400' : 'text-gray-400 hover:text-gray-200'} transition-colors"
				>
					{copied ? '복사됨' : '복사'}
				</button>
			</div>
		</div>
	{/if}

	{#if loading}
		<p class="text-sm text-gray-500">로딩 중...</p>
	{:else if attachments.length === 0}
		<p class="text-sm text-gray-500">연결된 파일 스토리지가 없습니다.</p>
	{:else}
		<div class="space-y-2">
			{#each attachments as att}
				<div class="flex items-start gap-3 p-3 bg-gray-800/50 rounded-lg border border-gray-700/50">
					<div class="flex-1 min-w-0">
						<div class="flex items-center gap-2">
							<span class="text-sm text-white font-medium truncate">{att.name || att.file_storage_id.slice(0, 12)}</span>
							{#if att.share_proto}
								<span class="text-[10px] text-gray-500 font-mono px-1.5 py-0.5 rounded bg-gray-700">{att.share_proto}</span>
							{/if}
							<span class="text-[10px] px-1.5 py-0.5 rounded font-mono {att.status === 'available' ? 'text-green-400 bg-green-900/20' : 'text-gray-400 bg-gray-700'}">{att.status}</span>
						</div>
					</div>
					<button
						onclick={() => handleDetach(att.file_storage_id)}
						disabled={detaching === att.file_storage_id}
						class="shrink-0 text-xs text-red-400/70 hover:text-red-400 disabled:text-gray-600 transition-colors"
					>
						{detaching === att.file_storage_id ? '해제 중...' : '해제'}
					</button>
				</div>
			{/each}
		</div>
	{/if}
</div>
