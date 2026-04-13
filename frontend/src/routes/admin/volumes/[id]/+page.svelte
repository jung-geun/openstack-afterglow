<script lang="ts">
	import { page } from '$app/stores';
	import { auth } from '$lib/stores/auth';
	import { untrack } from 'svelte';
	import { goto } from '$app/navigation';
	import { api, ApiError } from '$lib/api/client';
	import { projectNames } from '$lib/stores/projectNames';
	import { formatNumber } from '$lib/utils/format';

	interface AdminVolume {
		id: string;
		name: string;
		status: string;
		size: number;
		volume_type: string;
		project_id: string | null;
		attachments: { server_id: string; device: string; id: string }[];
		created_at: string | null;
		description: string;
		bootable: boolean | null;
		encrypted: boolean | null;
		multiattach: boolean | null;
		metadata: Record<string, string>;
	}

	const statusColor: Record<string, string> = {
		available:      'text-green-400 bg-green-900/30',
		'in-use':       'text-blue-400 bg-blue-900/30',
		creating:       'text-yellow-400 bg-yellow-900/30',
		error:          'text-red-400 bg-red-900/30',
		error_deleting: 'text-red-400 bg-red-900/30',
		deleting:       'text-orange-400 bg-orange-900/30',
		attaching:      'text-yellow-400 bg-yellow-900/30',
		detaching:      'text-yellow-400 bg-yellow-900/30',
		reserved:       'text-purple-400 bg-purple-900/30',
	};

	const volumeId = $derived($page.params.id);
	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	let volume = $state<AdminVolume | null>(null);
	let loading = $state(true);
	let error = $state('');
	let deleting = $state(false);

	// 상태 초기화
	let showReset = $state(false);
	let resetStatus = $state('available');
	let resetting = $state(false);

	// 용량 확장
	let showExtend = $state(false);
	let newSize = $state(0);
	let extending = $state(false);

	async function fetchVolume() {
		if (!volumeId) return;
		try {
			volume = await api.get<AdminVolume>(`/api/admin/volumes/${volumeId}`, token, projectId);
			newSize = volume.size + 10;
			error = '';
		} catch (e) {
			error = e instanceof ApiError ? `조회 실패 (${e.status})` : '서버 오류';
		} finally {
			loading = false;
		}
	}

	async function deleteVolume() {
		if (!volume || !confirm(`볼륨 "${volume.name || volume.id}"을 삭제하시겠습니까?`)) return;
		deleting = true;
		try {
			await api.delete(`/api/admin/volumes/${volumeId}`, token, projectId);
			goto('/admin/volumes');
		} catch (e) {
			alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
			deleting = false;
		}
	}

	async function resetVolumeStatus() {
		resetting = true;
		try {
			await api.post(`/api/admin/volumes/${volumeId}/reset-status`, { status: resetStatus }, token, projectId);
			showReset = false;
			await fetchVolume();
		} catch (e) {
			alert('상태 초기화 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			resetting = false;
		}
	}

	async function extendVolume() {
		if (!volume || newSize <= volume.size) {
			alert('새 크기는 현재 크기보다 커야 합니다.');
			return;
		}
		extending = true;
		try {
			await api.post(`/api/admin/volumes/${volumeId}/extend`, { new_size: newSize }, token, projectId);
			showExtend = false;
			await fetchVolume();
		} catch (e) {
			alert('확장 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			extending = false;
		}
	}

	$effect(() => {
		if (!$auth.projectId || !volumeId) return;
		loading = true;
		untrack(() => {
			fetchVolume();
			projectNames.load(token, projectId);
		});
	});
</script>

<div class="p-4 md:p-8 max-w-4xl">
	<div class="flex items-center gap-3 mb-6">
		<a href="/admin/volumes" class="text-gray-400 hover:text-white text-sm transition-colors">← 전체 볼륨</a>
	</div>

	{#if loading}
		<div class="animate-pulse space-y-4">
			<div class="h-8 bg-gray-800 rounded w-64"></div>
			<div class="h-40 bg-gray-800 rounded"></div>
		</div>
	{:else if error}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">{error}</div>
	{:else if volume}
		<div class="flex items-start justify-between mb-6">
			<div>
				<h1 class="text-2xl font-bold text-white">{volume.name || volume.id.slice(0, 12)}</h1>
				<div class="flex items-center gap-2 mt-1.5">
					<span class="px-2 py-0.5 rounded text-xs font-medium {statusColor[volume.status] ?? 'text-gray-400 bg-gray-800'}">
						{volume.status}
					</span>
					<span class="text-xs text-gray-500">{formatNumber(volume.size)} GB</span>
				</div>
			</div>
			<div class="flex items-center gap-2">
				<button
					onclick={() => { showExtend = true; }}
					class="px-3 py-1.5 bg-blue-900/40 hover:bg-blue-800/40 border border-blue-800 text-blue-400 text-sm rounded-lg transition-colors"
				>확장</button>
				{#if volume.status === 'error' || volume.status === 'error_deleting'}
					<button
						onclick={() => { showReset = true; }}
						class="px-3 py-1.5 bg-yellow-900/40 hover:bg-yellow-800/40 border border-yellow-800 text-yellow-400 text-sm rounded-lg transition-colors"
					>상태 초기화</button>
				{/if}
				<button
					onclick={deleteVolume}
					disabled={deleting || volume.status === 'in-use'}
					class="px-3 py-1.5 bg-red-900/40 hover:bg-red-900/60 border border-red-800 text-red-400 text-sm rounded-lg transition-colors disabled:opacity-50"
				>{deleting ? '삭제 중...' : '삭제'}</button>
			</div>
		</div>

		<div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
			<!-- 기본 정보 -->
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
				<h3 class="text-xs text-gray-500 uppercase tracking-wide mb-3">기본 정보</h3>
				<dl class="space-y-2 text-sm">
					<div class="flex justify-between">
						<dt class="text-gray-400">ID</dt>
						<dd class="font-mono text-xs text-gray-300">{volume.id}</dd>
					</div>
					<div class="flex justify-between">
						<dt class="text-gray-400">볼륨 타입</dt>
						<dd class="text-gray-300">{volume.volume_type || '-'}</dd>
					</div>
					<div class="flex justify-between">
						<dt class="text-gray-400">프로젝트</dt>
						<dd class="text-gray-300">{volume.project_id ? ($projectNames.get(volume.project_id) ?? volume.project_id.slice(0, 12)) : '-'}</dd>
					</div>
					<div class="flex justify-between">
						<dt class="text-gray-400">생성일</dt>
						<dd class="text-gray-300">{volume.created_at ? volume.created_at.slice(0, 10) : '-'}</dd>
					</div>
					{#if volume.description}
						<div class="flex justify-between">
							<dt class="text-gray-400">설명</dt>
							<dd class="text-gray-300 text-right max-w-48 break-words">{volume.description}</dd>
						</div>
					{/if}
				</dl>
			</div>

			<!-- 속성 -->
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
				<h3 class="text-xs text-gray-500 uppercase tracking-wide mb-3">속성</h3>
				<dl class="space-y-2 text-sm">
					<div class="flex justify-between">
						<dt class="text-gray-400">부팅 가능</dt>
						<dd class="text-gray-300">{volume.bootable === true ? '예' : volume.bootable === false ? '아니오' : '-'}</dd>
					</div>
					<div class="flex justify-between">
						<dt class="text-gray-400">암호화</dt>
						<dd class="text-gray-300">{volume.encrypted === true ? '예' : volume.encrypted === false ? '아니오' : '-'}</dd>
					</div>
					<div class="flex justify-between">
						<dt class="text-gray-400">멀티 연결</dt>
						<dd class="text-gray-300">{volume.multiattach === true ? '예' : volume.multiattach === false ? '아니오' : '-'}</dd>
					</div>
				</dl>
			</div>
		</div>

		<!-- 연결 정보 -->
		{#if volume.attachments.length > 0}
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-4 mb-4">
				<h3 class="text-xs text-gray-500 uppercase tracking-wide mb-3">연결 정보</h3>
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
							<th class="text-left py-1.5 pr-4">인스턴스 ID</th>
							<th class="text-left py-1.5 pr-4">디바이스</th>
						</tr>
					</thead>
					<tbody>
						{#each volume.attachments as att}
							<tr class="border-b border-gray-800/50 text-xs">
								<td class="py-2 pr-4 font-mono text-gray-300">{att.server_id}</td>
								<td class="py-2 pr-4 text-gray-400">{att.device}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}

		<!-- 메타데이터 -->
		{#if Object.keys(volume.metadata).length > 0}
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
				<h3 class="text-xs text-gray-500 uppercase tracking-wide mb-3">메타데이터</h3>
				<dl class="space-y-1.5 text-xs">
					{#each Object.entries(volume.metadata) as [k, v]}
						<div class="flex justify-between gap-4">
							<dt class="text-gray-400 font-mono">{k}</dt>
							<dd class="text-gray-300 font-mono text-right break-all">{v}</dd>
						</div>
					{/each}
				</dl>
			</div>
		{/if}
	{/if}
</div>

<!-- 용량 확장 모달 -->
{#if showExtend && volume}
	<div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onclick={() => { showExtend = false; }} role="dialog" onkeydown={(e) => e.key === 'Escape' && (showExtend = false)} tabindex="-1">
		<div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-sm mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()}>
			<h2 class="text-lg font-semibold text-white mb-4">볼륨 확장</h2>
			<p class="text-sm text-gray-400 mb-4">현재 크기: {formatNumber(volume.size)} GB</p>
			<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">새 크기 (GB)</label>
			<input bind:value={newSize} type="number" min={volume.size + 1} class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mb-4" />
			<div class="flex gap-3 justify-end">
				<button onclick={() => { showExtend = false; }} class="px-4 py-2 text-sm text-gray-400 hover:text-white">취소</button>
				<button onclick={extendVolume} disabled={extending} class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg disabled:opacity-30">
					{extending ? '확장 중...' : '확장'}
				</button>
			</div>
		</div>
	</div>
{/if}

<!-- 상태 초기화 모달 -->
{#if showReset && volume}
	<div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onclick={() => { showReset = false; }} role="dialog" onkeydown={(e) => e.key === 'Escape' && (showReset = false)} tabindex="-1">
		<div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-sm mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()}>
			<h2 class="text-lg font-semibold text-white mb-4">상태 초기화</h2>
			<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">변경할 상태</label>
			<select bind:value={resetStatus} class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mb-4">
				<option value="available">available</option>
				<option value="error">error</option>
				<option value="in-use">in-use</option>
			</select>
			<div class="flex gap-3 justify-end">
				<button onclick={() => { showReset = false; }} class="px-4 py-2 text-sm text-gray-400 hover:text-white">취소</button>
				<button onclick={resetVolumeStatus} disabled={resetting} class="px-4 py-2 bg-yellow-600 hover:bg-yellow-500 text-white text-sm rounded-lg disabled:opacity-30">
					{resetting ? '처리 중...' : '초기화'}
				</button>
			</div>
		</div>
	</div>
{/if}
