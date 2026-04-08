<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import TimeSeriesChart from '$lib/components/TimeSeriesChart.svelte';

	interface NetworkInfo {
		id: string;
		name: string;
		status: string;
		subnets: string[];
		is_external: boolean;
		is_shared: boolean;
	}
	interface TsPoint {
		ts: number;
		total?: number;
		[key: string]: number | undefined;
	}

	let networks = $state<NetworkInfo[]>([]);
	let loading = $state(true);
	let tsData = $state<TsPoint[]>([]);
	let tsRange = $state('7d');
	let tsLoading = $state(true);

	// 생성 모달
	let showCreate = $state(false);
	let creating = $state(false);
	let createError = $state('');
	let form = $state({ name: '', cidr: '', is_external: false, is_shared: false, enable_dhcp: true });

	// 수정 모달
	let editNet = $state<NetworkInfo | null>(null);
	let editName = $state('');
	let editShared = $state(false);
	let updating = $state(false);
	let editError = $state('');

	// 삭제 확인
	let deleteNet = $state<NetworkInfo | null>(null);
	let deleting = $state(false);
	let deleteError = $state('');

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function loadNetworks() {
		loading = true;
		try {
			networks = await api.get<NetworkInfo[]>('/api/admin/all-networks', token, projectId);
		} catch {
			networks = [];
		} finally {
			loading = false;
		}
	}

	async function loadTimeseries(range: string) {
		tsLoading = true;
		try {
			tsData = await api.get<TsPoint[]>(`/api/admin/timeseries/networks?range=${range}`, token, projectId);
		} catch {
			tsData = [];
		} finally {
			tsLoading = false;
		}
	}

	async function createNetwork() {
		creating = true; createError = '';
		try {
			await api.post('/api/admin/networks', {
				name: form.name,
				cidr: form.cidr || null,
				is_external: form.is_external,
				is_shared: form.is_shared,
				enable_dhcp: form.enable_dhcp,
			}, token, projectId);
			showCreate = false; form = { name: '', cidr: '', is_external: false, is_shared: false, enable_dhcp: true };
			await loadNetworks();
		} catch (e) { createError = e instanceof ApiError ? e.message : '생성 실패'; } finally { creating = false; }
	}

	async function updateNetwork() {
		if (!editNet) return;
		updating = true; editError = '';
		try {
			await api.put(`/api/admin/networks/${editNet.id}`, { name: editName, is_shared: editShared }, token, projectId);
			editNet = null; await loadNetworks();
		} catch (e) { editError = e instanceof ApiError ? e.message : '수정 실패'; } finally { updating = false; }
	}

	async function confirmDelete() {
		if (!deleteNet) return;
		deleting = true; deleteError = '';
		try {
			await api.delete(`/api/admin/networks/${deleteNet.id}`, token, projectId);
			deleteNet = null; await loadNetworks();
		} catch (e) { deleteError = e instanceof ApiError ? e.message : '삭제 실패'; } finally { deleting = false; }
	}

	onMount(() => { loadNetworks(); loadTimeseries(tsRange); });
</script>

<div class="p-4 md:p-8 max-w-6xl">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-white">전체 네트워크</h1>
		<div class="flex items-center gap-3">
			<button onclick={() => { showCreate = true; createError = ''; }} class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg">+ 생성</button>
			<button onclick={loadNetworks} class="text-xs text-gray-400 hover:text-white px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600">새로고침</button>
		</div>
	</div>

	<div class="mb-6">
		{#if tsLoading}
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-5 h-48 flex items-center justify-center">
				<div class="text-gray-600 text-sm">차트 로딩 중...</div>
			</div>
		{:else}
			<TimeSeriesChart
				data={tsData}
				title="네트워크 수 추이"
				mainKey="total"
				extraKeys={['routers', 'floating_ips_used']}
				currentRange={tsRange}
				onRangeChange={(r) => { tsRange = r; loadTimeseries(r); }}
			/>
		{/if}
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
						<th class="text-left py-2 pr-4">유형</th>
						<th class="text-left py-2 pr-4">서브넷</th>
						<th class="text-left py-2">액션</th>
					</tr>
				</thead>
				<tbody>
					{#each networks as n (n.id)}
						<tr class="border-b border-gray-800/50 text-xs hover:bg-gray-800/30 transition-colors">
							<td class="py-2 pr-4 text-white">{n.name || n.id.slice(0, 8)}</td>
							<td class="py-2 pr-4 {n.status === 'ACTIVE' ? 'text-green-400' : 'text-gray-400'}">{n.status}</td>
							<td class="py-2 pr-4">
								{#if n.is_external}<span class="px-1.5 py-0.5 bg-orange-900/30 text-orange-300 rounded text-xs mr-1">외부</span>{/if}
								{#if n.is_shared}<span class="px-1.5 py-0.5 bg-blue-900/30 text-blue-300 rounded text-xs">공유</span>{/if}
								{#if !n.is_external && !n.is_shared}<span class="text-gray-500">내부</span>{/if}
							</td>
							<td class="py-2 pr-4 text-gray-500">{n.subnets.length}개</td>
							<td class="py-2">
								<div class="flex items-center gap-1">
									<button onclick={() => { editNet = n; editName = n.name; editShared = n.is_shared; editError = ''; }}
										class="px-2 py-0.5 text-xs bg-gray-700 hover:bg-gray-600 text-gray-300 rounded">수정</button>
									<button onclick={() => { deleteNet = n; deleteError = ''; }}
										class="px-2 py-0.5 text-xs bg-red-900/30 hover:bg-red-900/50 text-red-400 rounded">삭제</button>
								</div>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		<div class="mt-3 text-xs text-gray-600">총 {networks.length}개 네트워크</div>
	{/if}
</div>

<!-- 생성 모달 -->
{#if showCreate}
	<div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onclick={() => { showCreate = false; createError = ''; }} role="dialog" onkeydown={(e) => e.key === 'Escape' && (showCreate = false)} tabindex="-1">
		<div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()}>
			<h2 class="text-lg font-semibold text-white mb-5">네트워크 생성</h2>
			{#if createError}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{createError}</div>{/if}
			<div class="space-y-4">
				<div><label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름</label><input bind:value={form.name} type="text" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" /></div>
				<div><label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">CIDR <span class="text-gray-600">(서브넷 자동 생성, 선택)</span></label><input bind:value={form.cidr} type="text" placeholder="예: 192.168.1.0/24" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" /></div>
				<div class="flex items-center gap-4">
					<label class="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
						<input type="checkbox" bind:checked={form.is_external} class="rounded" /> 외부 네트워크
					</label>
					<label class="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
						<input type="checkbox" bind:checked={form.is_shared} class="rounded" /> 공유
					</label>
				</div>
			</div>
			<div class="flex justify-end gap-3 mt-6">
				<button onclick={() => { showCreate = false; createError = ''; }} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">취소</button>
				<button onclick={createNetwork} disabled={creating || !form.name} class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg disabled:opacity-30">{creating ? '생성 중...' : '생성'}</button>
			</div>
		</div>
	</div>
{/if}

<!-- 수정 모달 -->
{#if editNet}
	<div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onclick={() => { editNet = null; }} role="dialog" onkeydown={(e) => e.key === 'Escape' && (editNet = null)} tabindex="-1">
		<div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()}>
			<h2 class="text-lg font-semibold text-white mb-5">네트워크 수정</h2>
			{#if editError}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{editError}</div>{/if}
			<div class="space-y-4">
				<div><label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름</label><input bind:value={editName} type="text" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" /></div>
				<label class="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
					<input type="checkbox" bind:checked={editShared} class="rounded" /> 공유
				</label>
			</div>
			<div class="flex justify-end gap-3 mt-6">
				<button onclick={() => { editNet = null; }} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">취소</button>
				<button onclick={updateNetwork} disabled={updating} class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg disabled:opacity-30">{updating ? '수정 중...' : '수정'}</button>
			</div>
		</div>
	</div>
{/if}

<!-- 삭제 확인 모달 -->
{#if deleteNet}
	<div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onclick={() => { deleteNet = null; }} role="dialog" onkeydown={(e) => e.key === 'Escape' && (deleteNet = null)} tabindex="-1">
		<div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-sm mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()}>
			<h2 class="text-lg font-semibold text-white mb-3">네트워크 삭제</h2>
			<p class="text-sm text-gray-400 mb-4"><span class="text-white">{deleteNet.name || deleteNet.id.slice(0, 8)}</span> 네트워크를 삭제하시겠습니까?</p>
			{#if deleteError}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{deleteError}</div>{/if}
			<div class="flex justify-end gap-3">
				<button onclick={() => { deleteNet = null; }} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">취소</button>
				<button onclick={confirmDelete} disabled={deleting} class="px-4 py-2 bg-red-600 hover:bg-red-500 text-white text-sm font-medium rounded-lg disabled:opacity-30">{deleting ? '삭제 중...' : '삭제'}</button>
			</div>
		</div>
	</div>
{/if}
