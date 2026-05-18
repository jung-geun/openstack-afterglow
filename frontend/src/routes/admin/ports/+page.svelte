<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import { projectNames } from '$lib/stores/projectNames';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import PortsTable from '$lib/components/admin/ports/PortsTable.svelte';
	import PortCreateModal from '$lib/components/admin/ports/PortCreateModal.svelte';
	import PortEditModal from '$lib/components/admin/ports/PortEditModal.svelte';
	import type { PortInfo, NetworkInfo } from '$lib/types/resources';
	import type { PagedResponse, ProjectName } from '$lib/types/adminPort';

	let ports = $state<PortInfo[]>([]);
	let loading = $state(true);
	let pageSize = $state(20);
	let markerStack = $state<string[]>([]);
	let nextMarker = $state<string | null>(null);
	let filter = $state('');
	let projectFilter = $state('');
	let allProjects = $state<ProjectName[]>([]);
	let allNetworks = $state<NetworkInfo[]>([]);

	// 수정 모달
	let editPort = $state<PortInfo | null>(null);
	let updating = $state(false);
	let editError = $state('');

	// 삭제 확인
	let deletePort = $state<PortInfo | null>(null);
	let deleting = $state(false);
	let deleteError = $state('');

	// 포트 생성 모달
	let showCreate = $state(false);
	let creating = $state(false);
	let createError = $state('');

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	const filtered = $derived(
		filter
			? ports.filter(p =>
				p.name?.includes(filter) ||
				p.device_owner?.includes(filter) ||
				p.fixed_ips.some(ip => ip.ip_address?.includes(filter)) ||
				(p.project_id && ($projectNames.get(p.project_id) ?? p.project_id)?.includes(filter))
			)
			: ports
	);

	async function load(marker?: string) {
		loading = true;
		try {
			let url = `/api/admin/all-ports?limit=${pageSize}`;
			if (marker) url += `&marker=${marker}`;
			if (projectFilter) url += `&project_id=${encodeURIComponent(projectFilter)}`;
			const res = await api.get<PagedResponse<PortInfo>>(url, token, projectId);
			ports = res.items || [];
			nextMarker = res.next_marker;
		} catch {
			ports = [];
		} finally {
			loading = false;
		}
	}

	async function loadProjects() {
		try {
			allProjects = await api.get<ProjectName[]>('/api/admin/projects/names', token, projectId);
		} catch { allProjects = []; }
	}

	async function loadNetworks() {
		try {
			allNetworks = await api.get<NetworkInfo[]>('/api/admin/all-networks', token, projectId);
		} catch { allNetworks = []; }
	}

	async function updatePort(name: string): Promise<boolean> {
		if (!editPort) return false;
		updating = true; editError = '';
		try {
			await api.put(`/api/admin/ports/${editPort.id}`, { name }, token, projectId);
			editPort = null;
			await load(markerStack[markerStack.length - 1]);
			return true;
		} catch (e) { editError = e instanceof ApiError ? e.message : '수정 실패'; return false; } finally { updating = false; }
	}

	async function confirmDelete() {
		if (!deletePort) return;
		deleting = true; deleteError = '';
		try {
			await api.delete(`/api/admin/ports/${deletePort.id}`, token, projectId);
			deletePort = null; await load(markerStack[markerStack.length - 1]);
		} catch (e) { deleteError = e instanceof ApiError ? e.message : '삭제 실패'; } finally { deleting = false; }
	}

	async function createPort(form: { network_id: string; name: string; project_id: string; fixed_ip: string }): Promise<boolean> {
		creating = true; createError = '';
		try {
			await api.post('/api/admin/ports', {
				network_id: form.network_id,
				name: form.name || undefined,
				project_id: form.project_id || undefined,
				fixed_ip: form.fixed_ip || undefined,
			}, token, projectId);
			showCreate = false;
			markerStack = []; nextMarker = null;
			await load();
			return true;
		} catch (e) { createError = e instanceof ApiError ? e.message : '포트 생성 실패'; return false; } finally { creating = false; }
	}

	const ar = createAutoRefresh(
		() => { load(markerStack[markerStack.length - 1]); },
		{ storageKey: 'admin-ports', defaultInterval: 30, intervalOptions: [15, 30, 60] }
	);

	onMount(() => {
		load();
		loadProjects();
		loadNetworks();
		projectNames.load(token, projectId);
	});
</script>

<div class="p-4 md:p-8 max-w-7xl mx-auto">
	<PageHeader breadcrumb="NETWORK / PORTS" title="포트">
		{#snippet actions()}
			<button onclick={() => { showCreate = true; createError = ''; }} class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg">+ 생성</button>
			<AutoRefreshControl
				bind:active={ar.active}
				bind:intervalSeconds={ar.intervalSeconds}
				intervalOptions={ar.intervalOptions}
				refreshing={loading}
				onManualRefresh={() => { markerStack = []; nextMarker = null; load(); }}
			/>
			<div class="flex items-center gap-1 text-xs text-gray-500">
				표시:
				{#each [10, 20, 30] as n}
					<button
						onclick={() => { pageSize = n; markerStack = []; nextMarker = null; load(); }}
						class="px-2 py-0.5 rounded {pageSize === n ? 'bg-blue-600 text-white' : 'bg-gray-800 hover:bg-gray-700 text-gray-400'}"
					>{n}</button>
				{/each}
			</div>
		{/snippet}
	</PageHeader>

	<!-- 필터 -->
	<div class="flex flex-wrap gap-3 mb-4">
		<input
			type="text"
			bind:value={filter}
			placeholder="필터 (이름, device_owner, IP)"
			class="text-xs bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-gray-300 placeholder-gray-600 w-56"
		/>
		<select bind:value={projectFilter} onchange={() => { markerStack = []; nextMarker = null; load(); }} class="text-xs bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-gray-300 focus:outline-none focus:border-blue-500">
			<option value="">전체 프로젝트</option>
			{#each allProjects as p (p.id)}
				<option value={p.id}>{p.name}</option>
			{/each}
		</select>
	</div>

	{#if loading}
		<div class="text-gray-500 text-sm">로딩 중...</div>
	{:else}
		<PortsTable
			ports={filtered}
			{markerStack}
			{nextMarker}
			onEdit={(p) => { editPort = p; editError = ''; }}
			onDelete={(p) => { deletePort = p; deleteError = ''; }}
			onPrev={() => {
				const prev = markerStack.slice(0, -1);
				const marker = prev[prev.length - 1];
				markerStack = prev;
				load(marker);
			}}
			onNext={() => {
				if (!nextMarker) return;
				markerStack = [...markerStack, nextMarker];
				load(nextMarker);
			}}
		/>
	{/if}
</div>

<PortCreateModal
	bind:open={showCreate}
	{allNetworks}
	{allProjects}
	{creating}
	error={createError}
	onCreate={createPort}
/>

<PortEditModal
	bind:target={editPort}
	{updating}
	error={editError}
	onSave={updatePort}
/>

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
