<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';

	interface PortInfo {
		id: string;
		name: string;
		status: string;
		network_id: string;
		device_owner: string;
		device_id: string;
		mac_address: string;
		fixed_ips: { ip_address: string; subnet_id: string }[];
		project_id: string | null;
	}

	let ports = $state<PortInfo[]>([]);
	let loading = $state(true);
	let filter = $state('');

	// 수정 모달
	let editPort = $state<PortInfo | null>(null);
	let editName = $state('');
	let updating = $state(false);
	let editError = $state('');

	// 삭제 확인
	let deletePort = $state<PortInfo | null>(null);
	let deleting = $state(false);
	let deleteError = $state('');

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	const filtered = $derived(
		filter
			? ports.filter(p =>
				p.name?.includes(filter) ||
				p.device_owner?.includes(filter) ||
				p.fixed_ips.some(ip => ip.ip_address?.includes(filter)) ||
				p.project_id?.includes(filter)
			)
			: ports
	);

	async function load() {
		loading = true;
		try {
			ports = await api.get<PortInfo[]>('/api/admin/all-ports', token, projectId);
		} catch {
			ports = [];
		} finally {
			loading = false;
		}
	}

	async function updatePort() {
		if (!editPort) return;
		updating = true; editError = '';
		try {
			await api.put(`/api/admin/ports/${editPort.id}`, { name: editName }, token, projectId);
			editPort = null; await load();
		} catch (e) { editError = e instanceof ApiError ? e.message : '수정 실패'; } finally { updating = false; }
	}

	async function confirmDelete() {
		if (!deletePort) return;
		deleting = true; deleteError = '';
		try {
			await api.delete(`/api/admin/ports/${deletePort.id}`, token, projectId);
			deletePort = null; await load();
		} catch (e) { deleteError = e instanceof ApiError ? e.message : '삭제 실패'; } finally { deleting = false; }
	}

	onMount(load);
</script>

<div class="p-4 md:p-8 max-w-6xl">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-white">전체 포트</h1>
		<div class="flex items-center gap-3">
			<input
				type="text"
				bind:value={filter}
				placeholder="필터 (이름, device_owner, IP, 프로젝트)"
				class="text-xs bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-gray-300 placeholder-gray-600 w-64"
			/>
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
						<th class="text-left py-2 pr-4">이름/ID</th>
						<th class="text-left py-2 pr-4">상태</th>
						<th class="text-left py-2 pr-4">Device Owner</th>
						<th class="text-left py-2 pr-4">IP 주소</th>
						<th class="text-left py-2 pr-4">프로젝트</th>
						<th class="text-left py-2">액션</th>
					</tr>
				</thead>
				<tbody>
					{#each filtered as p (p.id)}
						<tr class="border-b border-gray-800/50 text-xs hover:bg-gray-800/30 transition-colors">
							<td class="py-2 pr-4">
								<div class="text-white">{p.name || '-'}</div>
								<div class="text-gray-600 font-mono">{p.id.slice(0, 12)}...</div>
							</td>
							<td class="py-2 pr-4 {p.status === 'ACTIVE' ? 'text-green-400' : 'text-gray-400'}">{p.status}</td>
							<td class="py-2 pr-4 text-gray-500 text-xs break-all max-w-[160px]">{p.device_owner || '-'}</td>
							<td class="py-2 pr-4 font-mono text-gray-400">
								{#each p.fixed_ips as ip}
									<div>{ip.ip_address}</div>
								{/each}
								{#if p.fixed_ips.length === 0}-{/if}
							</td>
							<td class="py-2 pr-4 text-gray-500 font-mono">{p.project_id?.slice(0, 8) ?? '-'}</td>
							<td class="py-2">
								{#if !p.device_owner || p.device_owner === ''}
									<div class="flex items-center gap-1">
										<button onclick={() => { editPort = p; editName = p.name; editError = ''; }}
											class="px-2 py-0.5 text-xs bg-gray-700 hover:bg-gray-600 text-gray-300 rounded">수정</button>
										<button onclick={() => { deletePort = p; deleteError = ''; }}
											class="px-2 py-0.5 text-xs bg-red-900/30 hover:bg-red-900/50 text-red-400 rounded">삭제</button>
									</div>
								{/if}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		<div class="mt-3 text-xs text-gray-600">
			{filtered.length}/{ports.length}개 포트
		</div>
	{/if}
</div>

<!-- 수정 모달 -->
{#if editPort}
	<div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onclick={() => { editPort = null; }} role="dialog" onkeydown={(e) => e.key === 'Escape' && (editPort = null)} tabindex="-1">
		<div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()}>
			<h2 class="text-lg font-semibold text-white mb-5">포트 수정</h2>
			{#if editError}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{editError}</div>{/if}
			<div><label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름</label><input bind:value={editName} type="text" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" /></div>
			<div class="flex justify-end gap-3 mt-6">
				<button onclick={() => { editPort = null; }} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">취소</button>
				<button onclick={updatePort} disabled={updating} class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg disabled:opacity-30">{updating ? '수정 중...' : '수정'}</button>
			</div>
		</div>
	</div>
{/if}

<!-- 삭제 확인 모달 -->
{#if deletePort}
	<div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onclick={() => { deletePort = null; }} role="dialog" onkeydown={(e) => e.key === 'Escape' && (deletePort = null)} tabindex="-1">
		<div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-sm mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()}>
			<h2 class="text-lg font-semibold text-white mb-3">포트 삭제</h2>
			<p class="text-sm text-gray-400 mb-4">포트 <span class="text-white font-mono">{deletePort.id.slice(0, 8)}...</span>을 삭제하시겠습니까?</p>
			{#if deleteError}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{deleteError}</div>{/if}
			<div class="flex justify-end gap-3">
				<button onclick={() => { deletePort = null; }} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">취소</button>
				<button onclick={confirmDelete} disabled={deleting} class="px-4 py-2 bg-red-600 hover:bg-red-500 text-white text-sm font-medium rounded-lg disabled:opacity-30">{deleting ? '삭제 중...' : '삭제'}</button>
			</div>
		</div>
	</div>
{/if}
