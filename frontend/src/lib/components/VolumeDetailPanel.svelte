<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import { formatStorage } from '$lib/utils/format';

	interface Volume {
		id: string;
		name: string;
		status: string;
		size: number;
		volume_type: string | null;
		attachments: Record<string, unknown>[];
	}

	interface Instance {
		id: string;
		name: string;
		status: string;
	}

	interface Snapshot {
		id: string;
		name: string;
		status: string;
		size: number;
		description: string;
		created_at: string | null;
	}

	interface Props {
		volumeId: string;
		onClose?: () => void;
		onDeleted?: () => void;
	}

	let { volumeId, onClose, onDeleted }: Props = $props();

	let volume = $state<Volume | null>(null);
	let snapshots = $state<Snapshot[]>([]);
	let instances = $state<Instance[]>([]);
	let loading = $state(true);
	let error = $state('');
	let deleting = $state(false);
	let deletingSnapshot = $state<string | null>(null);

	// Snapshot creation
	let showSnapshotForm = $state(false);
	let snapshotName = $state('');
	let snapshotDesc = $state('');
	let creatingSnapshot = $state(false);
	let snapshotError = $state('');

	// Attach modal
	let showAttachModal = $state(false);
	let attachInstanceId = $state('');
	let attaching = $state(false);
	let attachError = $state('');

	const statusColor: Record<string, string> = {
		available:          'text-green-400 bg-green-900/30',
		creating:           'text-amber-400 bg-amber-900/30',
		deleting:           'text-orange-400 bg-orange-900/30',
		error:              'text-red-400 bg-red-900/30',
		in_use:             'text-blue-400 bg-blue-900/30',
		reserved:           'text-purple-400 bg-purple-900/30',
		attaching:          'text-cyan-400 bg-cyan-900/30',
		detaching:          'text-amber-400 bg-amber-900/30',
		error_deleting:     'text-rose-400 bg-rose-900/30',
	};

	$effect(() => {
		if (!volumeId || !$auth.token) return;
		loading = true;
		error = '';
		fetchAll();
	});

	async function fetchAll() {
		try {
			const [vol, snaps] = await Promise.all([
				api.get<Volume>(`/api/volumes/${volumeId}`, $auth.token ?? undefined, $auth.projectId ?? undefined),
				api.get<Snapshot[]>(`/api/volume-snapshots?volume_id=${volumeId}`, $auth.token ?? undefined, $auth.projectId ?? undefined).catch(() => []),
			]);
			volume = vol;
			snapshots = snaps;
		} catch (e) {
			error = e instanceof ApiError ? e.message : '볼륨 정보를 불러올 수 없습니다';
		} finally {
			loading = false;
		}
	}

	async function openAttachModal() {
		showAttachModal = true;
		attachError = '';
		try {
			instances = await api.get<Instance[]>('/api/instances', $auth.token ?? undefined, $auth.projectId ?? undefined);
		} catch {
			instances = [];
		}
	}

	async function attachVolume() {
		if (!attachInstanceId) return;
		attaching = true;
		attachError = '';
		try {
			await api.post(
				`/api/instances/${attachInstanceId}/volumes`,
				{ volume_id: volumeId },
				$auth.token ?? undefined,
				$auth.projectId ?? undefined
			);
			showAttachModal = false;
			attachInstanceId = '';
			await fetchAll();
		} catch (e) {
			attachError = e instanceof ApiError ? e.message : '연결 실패';
		} finally {
			attaching = false;
		}
	}

	async function deleteVolume() {
		if (!volume) return;
		if (!confirm(`볼륨 "${volume.name || volumeId.slice(0, 8)}"을 삭제하시겠습니까?`)) return;
		deleting = true;
		try {
			await api.delete(`/api/volumes/${volumeId}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
			onDeleted?.();
			onClose?.();
		} catch (e) {
			alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			deleting = false;
		}
	}

	async function createSnapshot() {
		if (!snapshotName.trim()) return;
		creatingSnapshot = true;
		snapshotError = '';
		try {
			await api.post(
				'/api/volume-snapshots',
				{ volume_id: volumeId, name: snapshotName.trim(), description: snapshotDesc.trim() || undefined },
				$auth.token ?? undefined,
				$auth.projectId ?? undefined
			);
			snapshotName = '';
			snapshotDesc = '';
			showSnapshotForm = false;
			await fetchAll();
		} catch (e) {
			snapshotError = e instanceof ApiError ? e.message : '스냅샷 생성 실패';
		} finally {
			creatingSnapshot = false;
		}
	}

	async function deleteSnapshot(id: string, name: string) {
		if (!confirm(`스냅샷 "${name || id.slice(0, 8)}"을 삭제하시겠습니까?`)) return;
		deletingSnapshot = id;
		try {
			await api.delete(`/api/volume-snapshots/${id}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
			snapshots = snapshots.filter(s => s.id !== id);
		} catch (e) {
			alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			deletingSnapshot = null;
		}
	}
</script>

<div class="p-6">
	<!-- Header -->
	<div class="flex items-start justify-between mb-6">
		<div>
			<h2 class="text-xl font-bold text-white">{volume?.name || volumeId.slice(0, 8)}</h2>
			{#if volume}
				<span class="inline-block mt-1 px-2 py-0.5 rounded text-xs font-medium {statusColor[volume.status] ?? 'text-gray-400 bg-gray-800'}">{volume.status}</span>
			{/if}
		</div>
		<button onclick={onClose} class="text-gray-400 hover:text-white transition-colors text-lg leading-none">✕</button>
	</div>

	{#if loading}
		<div class="space-y-3">
			{#each [1,2,3] as _}
				<div class="h-12 bg-gray-800 rounded-lg animate-pulse"></div>
			{/each}
		</div>
	{:else if error}
		<div class="text-red-400 text-sm bg-red-900/20 border border-red-800 rounded-lg px-4 py-3">{error}</div>
	{:else if volume}
		<!-- Basic Info -->
		<div class="bg-gray-900 rounded-xl border border-gray-700 p-4 mb-4 space-y-2 text-sm">
			<div class="flex justify-between">
				<span class="text-gray-400">ID</span>
				<span class="text-white font-mono text-xs">{volume.id}</span>
			</div>
			<div class="flex justify-between">
				<span class="text-gray-400">크기</span>
				<span class="text-white">{formatStorage(volume.size)}</span>
			</div>
			<div class="flex justify-between">
				<span class="text-gray-400">타입</span>
				<span class="text-white">{volume.volume_type ?? '-'}</span>
			</div>
			<div class="flex justify-between">
				<span class="text-gray-400">연결</span>
				<span class="text-white">{volume.attachments.length > 0 ? `${volume.attachments.length}개 인스턴스` : '미연결'}</span>
			</div>
		</div>

		<!-- Attachments -->
		{#if volume.attachments.length > 0}
			<div class="mb-4">
				<h3 class="text-xs text-gray-400 uppercase tracking-wide mb-2">연결된 인스턴스</h3>
				<div class="space-y-1">
					{#each volume.attachments as att}
						<div class="bg-gray-900 rounded-lg border border-gray-700 px-3 py-2 text-xs text-gray-300">
							<span class="font-mono">{(att as Record<string, unknown>).server_id as string ?? '-'}</span>
							{#if (att as Record<string, unknown>).device}
								<span class="text-gray-500 ml-2">{(att as Record<string, unknown>).device as string}</span>
							{/if}
						</div>
					{/each}
				</div>
			</div>
		{/if}

		<!-- Snapshots -->
		<div class="mb-4">
			<div class="flex items-center justify-between mb-2">
				<h3 class="text-xs text-gray-400 uppercase tracking-wide">스냅샷</h3>
				<button
					onclick={() => { showSnapshotForm = !showSnapshotForm; snapshotError = ''; }}
					class="text-blue-400 hover:text-blue-300 text-xs transition-colors"
				>+ 스냅샷 생성</button>
			</div>

			{#if showSnapshotForm}
				<div class="bg-gray-900 border border-gray-700 rounded-lg p-3 mb-3 space-y-2">
					<input
						bind:value={snapshotName}
						type="text"
						placeholder="스냅샷 이름"
						class="w-full bg-gray-800 border border-gray-600 rounded px-2 py-1.5 text-sm text-white focus:outline-none focus:border-blue-500"
					/>
					<input
						bind:value={snapshotDesc}
						type="text"
						placeholder="설명 (선택)"
						class="w-full bg-gray-800 border border-gray-600 rounded px-2 py-1.5 text-sm text-white focus:outline-none focus:border-blue-500"
					/>
					{#if snapshotError}<p class="text-xs text-red-400">{snapshotError}</p>{/if}
					<div class="flex gap-2 justify-end">
						<button onclick={() => showSnapshotForm = false} class="text-xs text-gray-400 hover:text-white transition-colors">취소</button>
						<button
							onclick={createSnapshot}
							disabled={creatingSnapshot || !snapshotName.trim()}
							class="text-xs bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white px-3 py-1 rounded transition-colors"
						>{creatingSnapshot ? '생성 중...' : '생성'}</button>
					</div>
				</div>
			{/if}

			{#if snapshots.length === 0}
				<p class="text-xs text-gray-500">스냅샷이 없습니다.</p>
			{:else}
				<div class="space-y-1">
					{#each snapshots as snap}
						<div class="bg-gray-900 rounded-lg border border-gray-700 px-3 py-2 flex items-center justify-between text-xs">
							<div>
								<span class="text-white font-medium">{snap.name || snap.id.slice(0, 8)}</span>
								<span class="text-gray-500 ml-2">{formatStorage(snap.size)}</span>
								<span class="ml-2 px-1.5 py-0.5 rounded text-xs {statusColor[snap.status] ?? 'text-gray-400 bg-gray-800'}">{snap.status}</span>
							</div>
							<button
								onclick={() => deleteSnapshot(snap.id, snap.name)}
								disabled={deletingSnapshot === snap.id}
								class="text-red-400 hover:text-red-300 disabled:text-gray-600 transition-colors ml-2"
							>{deletingSnapshot === snap.id ? '...' : '삭제'}</button>
						</div>
					{/each}
				</div>
			{/if}
		</div>

		<!-- Actions -->
		<div class="flex gap-2 flex-wrap">
			{#if volume.status === 'available'}
				<button
					onclick={openAttachModal}
					class="px-3 py-1.5 text-xs bg-blue-600 hover:bg-blue-500 text-white rounded-lg transition-colors"
				>인스턴스에 연결</button>
			{/if}
			<button
				onclick={deleteVolume}
				disabled={deleting || volume.attachments.length > 0}
				class="px-3 py-1.5 text-xs bg-red-900/40 hover:bg-red-900/60 disabled:opacity-40 text-red-400 border border-red-900 rounded-lg transition-colors"
				title={volume.attachments.length > 0 ? '연결된 볼륨은 삭제할 수 없습니다' : ''}
			>{deleting ? '삭제 중...' : '볼륨 삭제'}</button>
		</div>
	{/if}
</div>

<!-- Attach Modal -->
{#if showAttachModal}
	<div class="fixed inset-0 bg-black/60 flex items-center justify-center z-[60]"
		onclick={() => { showAttachModal = false; attachError = ''; }}
		role="dialog" aria-modal="true" tabindex="-1"
		onkeydown={(e) => e.key === 'Escape' && (showAttachModal = false)}
	>
		<div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-sm mx-4 shadow-2xl"
			onclick={(e) => e.stopPropagation()} role="none" onkeydown={(e) => e.stopPropagation()}
		>
			<h3 class="text-base font-semibold text-white mb-4">인스턴스에 볼륨 연결</h3>
			<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">인스턴스 선택
				<select bind:value={attachInstanceId} class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5">
					<option value="">-- 선택 --</option>
					{#each instances as inst}
						<option value={inst.id}>{inst.name || inst.id.slice(0, 8)} ({inst.status})</option>
					{/each}
				</select>
			</label>
			{#if attachError}<p class="text-xs text-red-400 mt-2">{attachError}</p>{/if}
			<div class="flex justify-end gap-3 mt-5">
				<button onclick={() => { showAttachModal = false; attachError = ''; }} class="text-sm text-gray-400 hover:text-white transition-colors">취소</button>
				<button
					onclick={attachVolume}
					disabled={attaching || !attachInstanceId}
					class="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm rounded-lg transition-colors"
				>{attaching ? '연결 중...' : '연결'}</button>
			</div>
		</div>
	</div>
{/if}
