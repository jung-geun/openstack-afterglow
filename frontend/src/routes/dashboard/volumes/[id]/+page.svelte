<script lang="ts">
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import { formatStorage } from '$lib/utils/format';

	interface Volume {
		id: string;
		name: string;
		status: string;
		size: number;
		volume_type: string | null;
		attachments: Record<string, string>[];
	}

	interface Instance {
		id: string;
		name: string;
	}

	let volume = $state<Volume | null>(null);
	let attachedInstances = $state<Map<string, string>>(new Map());
	let loading = $state(true);
	let error = $state('');
	let deleting = $state(false);

	const statusColor: Record<string, string> = {
		available:          'text-green-400 bg-green-900/30',
		in_use:             'text-blue-400 bg-blue-900/30',
		creating:           'text-amber-400 bg-amber-900/30',
		deleting:           'text-orange-400 bg-orange-900/30',
		error:              'text-red-400 bg-red-900/30',
		reserved:           'text-purple-400 bg-purple-900/30',
		attaching:          'text-cyan-400 bg-cyan-900/30',
		detaching:          'text-amber-400 bg-amber-900/30',
		'backing-up':       'text-indigo-400 bg-indigo-900/30',
		'restoring-backup': 'text-teal-400 bg-teal-900/30',
		downloading:        'text-sky-400 bg-sky-900/30',
		uploading:          'text-sky-400 bg-sky-900/30',
		extending:          'text-cyan-400 bg-cyan-900/30',
		error_deleting:     'text-rose-400 bg-rose-900/30',
		error_backing_up:   'text-rose-400 bg-rose-900/30',
		error_restoring:    'text-rose-400 bg-rose-900/30',
		error_extending:    'text-rose-400 bg-rose-900/30',
	};

	$effect(() => {
		const id = $page.params.id;
		if (!id || !$auth.token) return;
		fetchVolume(id);
	});

	async function fetchVolume(id: string) {
		loading = true;
		error = '';
		try {
			volume = await api.get<Volume>(
				`/api/volumes/${id}`,
				$auth.token ?? undefined,
				$auth.projectId ?? undefined
			);
			// 연결된 인스턴스 이름 해소
			if (volume.attachments.length > 0) {
				const map = new Map<string, string>();
				await Promise.allSettled(
					volume.attachments.map(async (a) => {
						const serverId = a.server_id;
						if (!serverId) return;
						try {
							const inst = await api.get<Instance>(
								`/api/instances/${serverId}`,
								$auth.token ?? undefined,
								$auth.projectId ?? undefined
							);
							map.set(serverId, inst.name);
						} catch {
							map.set(serverId, serverId.slice(0, 8) + '…');
						}
					})
				);
				attachedInstances = map;
			}
		} catch (e) {
			error = e instanceof ApiError ? `조회 실패 (${e.status}): ${e.message}` : '서버 오류';
		} finally {
			loading = false;
		}
	}

	async function deleteVolume() {
		if (!volume) return;
		if (volume.attachments.length > 0) {
			alert('연결된 볼륨은 삭제할 수 없습니다. 먼저 인스턴스에서 분리하세요.');
			return;
		}
		if (!confirm(`볼륨 "${volume.name || volume.id}"을 삭제하시겠습니까?`)) return;
		deleting = true;
		try {
			await api.delete(`/api/volumes/${volume.id}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
			goto('/dashboard');
		} catch (e) {
			alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			deleting = false;
		}
	}
</script>

<div class="p-8 max-w-4xl mx-auto">
	<div class="mb-6">
		<a href="/dashboard" class="text-gray-400 hover:text-gray-200 text-sm transition-colors">
			← 대시보드
		</a>
	</div>

	{#if error}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">
			{error}
		</div>
	{:else if loading}
		<LoadingSkeleton variant="card" rows={5} />
	{:else if volume}
		<div class="flex items-start justify-between mb-6">
			<div>
				<h1 class="text-2xl font-bold text-white">
					{#if volume.name}
						{volume.name}
					{:else}
						<span class="font-mono text-gray-300">{volume.id}</span>
					{/if}
				</h1>
				<span
					class="mt-2 inline-block px-2 py-0.5 rounded text-xs font-medium {statusColor[volume.status] ?? 'text-gray-400 bg-gray-800'}"
				>
					{volume.status}
				</span>
			</div>
			<button
				onclick={deleteVolume}
				disabled={deleting || volume.attachments.length > 0}
				class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors"
				title={volume.attachments.length > 0 ? '연결된 볼륨은 삭제할 수 없습니다' : ''}
			>
				{deleting ? '삭제 중...' : '삭제'}
			</button>
		</div>

		<div class="bg-gray-900 border border-gray-800 rounded-lg p-6 mb-4">
			<h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-4">기본 정보</h2>
			<dl class="grid grid-cols-2 gap-x-8 gap-y-3">
				<div>
					<dt class="text-xs text-gray-500 mb-0.5">ID</dt>
					<dd class="text-sm text-gray-300 font-mono">{volume.id}</dd>
				</div>
				<div>
					<dt class="text-xs text-gray-500 mb-0.5">크기</dt>
					<dd class="text-sm text-gray-300">{formatStorage(volume.size)}</dd>
				</div>
				<div>
					<dt class="text-xs text-gray-500 mb-0.5">볼륨 타입</dt>
					<dd class="text-sm text-gray-300">{volume.volume_type ?? '-'}</dd>
				</div>
			</dl>
		</div>

		<div class="bg-gray-900 border border-gray-800 rounded-lg p-6">
			<h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-4">연결 정보</h2>
			{#if volume.attachments.length === 0}
				<p class="text-sm text-gray-500">미연결</p>
			{:else}
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
							<th class="text-left py-2 pr-6">인스턴스</th>
							<th class="text-left py-2 pr-6">디바이스</th>
							<th class="text-left py-2">ID</th>
						</tr>
					</thead>
					<tbody>
						{#each volume.attachments as a}
							<tr class="border-b border-gray-800/50">
								<td class="py-2 pr-6">
									<a
										href="/dashboard/instances/{a.server_id}"
										class="text-blue-400 hover:text-blue-300 transition-colors"
									>
										{attachedInstances.get(a.server_id) ?? a.server_id?.slice(0, 8) + '…'}
									</a>
								</td>
								<td class="py-2 pr-6 text-gray-400 font-mono text-xs">{a.device ?? '-'}</td>
								<td class="py-2 text-gray-500 font-mono text-xs">{a.server_id}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			{/if}
		</div>
	{/if}
</div>
