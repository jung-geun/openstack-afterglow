<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';

	interface RouterInfo {
		id: string;
		name: string;
		status: string;
		external_gateway_network_id: string | null;
		connected_subnet_ids: string[];
		project_id: string | null;
	}
	interface NetworkInfo {
		id: string;
		name: string;
		is_external: boolean;
	}

	let routers = $state<RouterInfo[]>([]);
	let loading = $state(true);

	// 생성 모달
	let showCreate = $state(false);
	let creating = $state(false);
	let createError = $state('');
	let externalNets = $state<NetworkInfo[]>([]);
	let form = $state({ name: '', external_network_id: '' });

	// 수정 모달
	let editRouter = $state<RouterInfo | null>(null);
	let editName = $state('');
	let updating = $state(false);
	let editError = $state('');

	// 삭제 확인
	let deleteRouter = $state<RouterInfo | null>(null);
	let deleting = $state(false);
	let deleteError = $state('');

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function load() {
		loading = true;
		try {
			routers = await api.get<RouterInfo[]>('/api/admin/all-routers', token, projectId);
		} catch {
			routers = [];
		} finally {
			loading = false;
		}
	}

	async function openCreate() {
		showCreate = true; createError = '';
		try {
			const nets = await api.get<NetworkInfo[]>('/api/admin/all-networks', token, projectId);
			externalNets = nets.filter(n => n.is_external);
			form.external_network_id = externalNets.length > 0 ? externalNets[0].id : '';
		} catch {
			externalNets = [];
		}
	}

	async function createRouter() {
		creating = true; createError = '';
		try {
			await api.post('/api/admin/routers', {
				name: form.name,
				external_network_id: form.external_network_id || null,
			}, token, projectId);
			showCreate = false; form = { name: '', external_network_id: '' }; await load();
		} catch (e) { createError = e instanceof ApiError ? e.message : '생성 실패'; } finally { creating = false; }
	}

	async function updateRouter() {
		if (!editRouter) return;
		updating = true; editError = '';
		try {
			await api.put(`/api/admin/routers/${editRouter.id}`, { name: editName }, token, projectId);
			editRouter = null; await load();
		} catch (e) { editError = e instanceof ApiError ? e.message : '수정 실패'; } finally { updating = false; }
	}

	async function confirmDelete() {
		if (!deleteRouter) return;
		deleting = true; deleteError = '';
		try {
			await api.delete(`/api/admin/routers/${deleteRouter.id}`, token, projectId);
			deleteRouter = null; await load();
		} catch (e) { deleteError = e instanceof ApiError ? e.message : '삭제 실패'; } finally { deleting = false; }
	}

	onMount(load);
</script>

<div class="p-4 md:p-8 max-w-6xl">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-white">전체 라우터</h1>
		<div class="flex items-center gap-3">
			<button onclick={openCreate} class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg">+ 생성</button>
			<button onclick={load} class="text-xs text-gray-400 hover:text-white px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600">새로고침</button>
		</div>
	</div>

	{#if loading}
		<div class="text-gray-500 text-sm">로딩 중...</div>
	{:else}
		<div class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
						<th class="text-left py-2 pr-4">이름</th>
						<th class="text-left py-2 pr-4">상태</th>
						<th class="text-left py-2 pr-4">외부 게이트웨이</th>
						<th class="text-left py-2 pr-4">연결 서브넷</th>
						<th class="text-left py-2 pr-4">프로젝트</th>
						<th class="text-left py-2">액션</th>
					</tr>
				</thead>
				<tbody>
					{#each routers as r (r.id)}
						<tr class="border-b border-gray-800/50 text-xs hover:bg-gray-800/30 transition-colors">
							<td class="py-2 pr-4 text-white">{r.name || r.id.slice(0, 8)}</td>
							<td class="py-2 pr-4 {r.status === 'ACTIVE' ? 'text-green-400' : 'text-gray-400'}">{r.status}</td>
							<td class="py-2 pr-4 text-gray-500 font-mono">
								{r.external_gateway_network_id ? r.external_gateway_network_id.slice(0, 8) + '...' : '-'}
							</td>
							<td class="py-2 pr-4 text-gray-500">{r.connected_subnet_ids.length}개</td>
							<td class="py-2 pr-4 text-gray-500 font-mono">{r.project_id?.slice(0, 8) ?? '-'}</td>
							<td class="py-2">
								<div class="flex items-center gap-1">
									<button onclick={() => { editRouter = r; editName = r.name; editError = ''; }}
										class="px-2 py-0.5 text-xs bg-gray-700 hover:bg-gray-600 text-gray-300 rounded">수정</button>
									<button onclick={() => { deleteRouter = r; deleteError = ''; }}
										class="px-2 py-0.5 text-xs bg-red-900/30 hover:bg-red-900/50 text-red-400 rounded">삭제</button>
								</div>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		<div class="mt-3 text-xs text-gray-600">총 {routers.length}개 라우터</div>
	{/if}
</div>

<!-- 생성 모달 -->
{#if showCreate}
	<div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onclick={() => { showCreate = false; }} role="dialog" onkeydown={(e) => e.key === 'Escape' && (showCreate = false)} tabindex="-1">
		<div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()}>
			<h2 class="text-lg font-semibold text-white mb-5">라우터 생성</h2>
			{#if createError}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{createError}</div>{/if}
			<div class="space-y-4">
				<div><label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름</label><input bind:value={form.name} type="text" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" /></div>
				<div>
					<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">외부 네트워크 <span class="text-gray-600">(선택)</span></label>
					<select bind:value={form.external_network_id} class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none">
						<option value="">없음</option>
						{#each externalNets as n}
							<option value={n.id}>{n.name || n.id.slice(0, 8)}</option>
						{/each}
					</select>
				</div>
			</div>
			<div class="flex justify-end gap-3 mt-6">
				<button onclick={() => { showCreate = false; }} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">취소</button>
				<button onclick={createRouter} disabled={creating || !form.name} class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg disabled:opacity-30">{creating ? '생성 중...' : '생성'}</button>
			</div>
		</div>
	</div>
{/if}

<!-- 수정 모달 -->
{#if editRouter}
	<div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onclick={() => { editRouter = null; }} role="dialog" onkeydown={(e) => e.key === 'Escape' && (editRouter = null)} tabindex="-1">
		<div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()}>
			<h2 class="text-lg font-semibold text-white mb-5">라우터 수정</h2>
			{#if editError}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{editError}</div>{/if}
			<div><label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름</label><input bind:value={editName} type="text" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" /></div>
			<div class="flex justify-end gap-3 mt-6">
				<button onclick={() => { editRouter = null; }} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">취소</button>
				<button onclick={updateRouter} disabled={updating} class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg disabled:opacity-30">{updating ? '수정 중...' : '수정'}</button>
			</div>
		</div>
	</div>
{/if}

<!-- 삭제 확인 모달 -->
{#if deleteRouter}
	<div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onclick={() => { deleteRouter = null; }} role="dialog" onkeydown={(e) => e.key === 'Escape' && (deleteRouter = null)} tabindex="-1">
		<div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-sm mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()}>
			<h2 class="text-lg font-semibold text-white mb-3">라우터 삭제</h2>
			<p class="text-sm text-gray-400 mb-4"><span class="text-white">{deleteRouter.name || deleteRouter.id.slice(0, 8)}</span> 라우터를 삭제하시겠습니까?</p>
			{#if deleteError}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{deleteError}</div>{/if}
			<div class="flex justify-end gap-3">
				<button onclick={() => { deleteRouter = null; }} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">취소</button>
				<button onclick={confirmDelete} disabled={deleting} class="px-4 py-2 bg-red-600 hover:bg-red-500 text-white text-sm font-medium rounded-lg disabled:opacity-30">{deleting ? '삭제 중...' : '삭제'}</button>
			</div>
		</div>
	</div>
{/if}
