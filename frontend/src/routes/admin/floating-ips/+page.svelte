<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';

	interface FloatingIpInfo {
		id: string;
		floating_ip_address: string;
		fixed_ip_address: string | null;
		status: string;
		port_id: string | null;
		project_id: string | null;
	}
	interface NetworkInfo {
		id: string;
		name: string;
		is_external: boolean;
	}

	let fips = $state<FloatingIpInfo[]>([]);
	let loading = $state(true);

	// 생성 모달
	let showCreate = $state(false);
	let creating = $state(false);
	let createError = $state('');
	let externalNets = $state<NetworkInfo[]>([]);
	let selectedNetId = $state('');

	// 삭제 확인
	let deleteFip = $state<FloatingIpInfo | null>(null);
	let deleting = $state(false);
	let deleteError = $state('');

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function load() {
		loading = true;
		try {
			fips = await api.get<FloatingIpInfo[]>('/api/admin/all-floating-ips', token, projectId);
		} catch {
			fips = [];
		} finally {
			loading = false;
		}
	}

	async function openCreate() {
		showCreate = true; createError = '';
		try {
			const nets = await api.get<NetworkInfo[]>('/api/admin/all-networks', token, projectId);
			externalNets = nets.filter(n => n.is_external);
			selectedNetId = externalNets.length > 0 ? externalNets[0].id : '';
		} catch {
			externalNets = [];
		}
	}

	async function createFip() {
		if (!selectedNetId) return;
		creating = true; createError = '';
		try {
			await api.post('/api/admin/floating-ips', { floating_network_id: selectedNetId }, token, projectId);
			showCreate = false; await load();
		} catch (e) { createError = e instanceof ApiError ? e.message : '생성 실패'; } finally { creating = false; }
	}

	async function confirmDelete() {
		if (!deleteFip) return;
		deleting = true; deleteError = '';
		try {
			await api.delete(`/api/admin/floating-ips/${deleteFip.id}`, token, projectId);
			deleteFip = null; await load();
		} catch (e) { deleteError = e instanceof ApiError ? e.message : '삭제 실패'; } finally { deleting = false; }
	}

	onMount(load);
</script>

<div class="p-4 md:p-8 max-w-6xl">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-white">전체 Floating IP</h1>
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
						<th class="text-left py-2 pr-4">Floating IP</th>
						<th class="text-left py-2 pr-4">Fixed IP</th>
						<th class="text-left py-2 pr-4">상태</th>
						<th class="text-left py-2 pr-4">프로젝트</th>
						<th class="text-left py-2">액션</th>
					</tr>
				</thead>
				<tbody>
					{#each fips as f (f.id)}
						<tr class="border-b border-gray-800/50 text-xs hover:bg-gray-800/30 transition-colors">
							<td class="py-2 pr-4 font-mono text-green-400">{f.floating_ip_address}</td>
							<td class="py-2 pr-4 font-mono text-gray-400">{f.fixed_ip_address ?? '-'}</td>
							<td class="py-2 pr-4 {f.port_id ? 'text-green-400' : 'text-gray-500'}">
								{f.port_id ? '할당됨' : '미할당'}
							</td>
							<td class="py-2 pr-4 text-gray-500 font-mono">{f.project_id?.slice(0, 8) ?? '-'}</td>
							<td class="py-2">
								{#if !f.port_id}
									<button onclick={() => { deleteFip = f; deleteError = ''; }}
										class="px-2 py-0.5 text-xs bg-red-900/30 hover:bg-red-900/50 text-red-400 rounded">삭제</button>
								{/if}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		<div class="mt-3 flex gap-4 text-xs text-gray-500">
			<span>총 {fips.length}개</span>
			<span class="text-green-400">할당됨: {fips.filter(f => f.port_id).length}개</span>
			<span>미할당: {fips.filter(f => !f.port_id).length}개</span>
		</div>
	{/if}
</div>

<!-- 생성 모달 -->
{#if showCreate}
	<div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onclick={() => { showCreate = false; }} role="dialog" onkeydown={(e) => e.key === 'Escape' && (showCreate = false)} tabindex="-1">
		<div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()}>
			<h2 class="text-lg font-semibold text-white mb-5">Floating IP 생성</h2>
			{#if createError}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{createError}</div>{/if}
			<div>
				<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">외부 네트워크</label>
				{#if externalNets.length === 0}
					<div class="text-xs text-red-400">외부 네트워크가 없습니다</div>
				{:else}
					<select bind:value={selectedNetId} class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none">
						{#each externalNets as n}
							<option value={n.id}>{n.name || n.id.slice(0, 8)}</option>
						{/each}
					</select>
				{/if}
			</div>
			<div class="flex justify-end gap-3 mt-6">
				<button onclick={() => { showCreate = false; }} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">취소</button>
				<button onclick={createFip} disabled={creating || !selectedNetId} class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg disabled:opacity-30">{creating ? '생성 중...' : '생성'}</button>
			</div>
		</div>
	</div>
{/if}

<!-- 삭제 확인 모달 -->
{#if deleteFip}
	<div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onclick={() => { deleteFip = null; }} role="dialog" onkeydown={(e) => e.key === 'Escape' && (deleteFip = null)} tabindex="-1">
		<div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-sm mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()}>
			<h2 class="text-lg font-semibold text-white mb-3">Floating IP 삭제</h2>
			<p class="text-sm text-gray-400 mb-4"><span class="text-white font-mono">{deleteFip.floating_ip_address}</span>을 삭제하시겠습니까?</p>
			{#if deleteError}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{deleteError}</div>{/if}
			<div class="flex justify-end gap-3">
				<button onclick={() => { deleteFip = null; }} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">취소</button>
				<button onclick={confirmDelete} disabled={deleting} class="px-4 py-2 bg-red-600 hover:bg-red-500 text-white text-sm font-medium rounded-lg disabled:opacity-30">{deleting ? '삭제 중...' : '삭제'}</button>
			</div>
		</div>
	</div>
{/if}
