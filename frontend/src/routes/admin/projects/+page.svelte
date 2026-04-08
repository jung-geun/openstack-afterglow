<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';

	interface Project {
		id: string;
		name: string;
		description: string;
		enabled: boolean;
		domain_id: string | null;
		created_at: string | null;
	}
	interface PagedResponse<T> {
		items: T[];
		next_marker: string | null;
		count: number;
	}

	let projects = $state<Project[]>([]);
	let loading = $state(true);
	let pageSize = $state(20);
	let markerStack = $state<string[]>([]);
	let nextMarker = $state<string | null>(null);

	let showCreate = $state(false);
	let creating = $state(false);
	let createError = $state('');
	let form = $state({ name: '', description: '', enabled: true });

	let editProject = $state<Project | null>(null);
	let editName = $state('');
	let editDesc = $state('');
	let editEnabled = $state(true);
	let updating = $state(false);
	let editError = $state('');

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function load(marker?: string) {
		loading = true;
		try {
			let url = `/api/admin/projects?limit=${pageSize}`;
			if (marker) url += `&marker=${marker}`;
			const res = await api.get<PagedResponse<Project>>(url, token, projectId);
			projects = res.items; nextMarker = res.next_marker;
		} catch { projects = []; } finally { loading = false; }
	}

	async function createProject() {
		creating = true; createError = '';
		try {
			await api.post('/api/admin/projects', { name: form.name, description: form.description || null, enabled: form.enabled }, token, projectId);
			showCreate = false; form = { name: '', description: '', enabled: true }; await load();
		} catch (e) { createError = e instanceof ApiError ? e.message : '생성 실패'; } finally { creating = false; }
	}

	async function updateProject() {
		if (!editProject) return;
		updating = true; editError = '';
		try {
			await api.patch(`/api/admin/projects/${editProject.id}`, { name: editName, description: editDesc || null, enabled: editEnabled }, token, projectId);
			editProject = null; await load();
		} catch (e) { editError = e instanceof ApiError ? e.message : '수정 실패'; } finally { updating = false; }
	}

	onMount(load);
</script>

<div class="p-4 md:p-8 max-w-6xl">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-white">프로젝트 관리</h1>
		<div class="flex items-center gap-3">
			<button onclick={() => { showCreate = true; createError = ''; }} class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg">+ 생성</button>
			<button onclick={() => load()} class="text-xs text-gray-400 hover:text-white transition-colors px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600">새로고침</button>
			<div class="flex items-center gap-1 text-xs text-gray-500">
				표시:
				{#each [10, 20, 30] as n}
					<button onclick={() => { pageSize = n; markerStack = []; nextMarker = null; load(); }}
						class="px-2 py-0.5 rounded {pageSize === n ? 'bg-blue-600 text-white' : 'bg-gray-800 hover:bg-gray-700 text-gray-400'}">{n}</button>
				{/each}
			</div>
		</div>
	</div>

	{#if loading}
		<LoadingSkeleton variant="table" rows={5} />
	{:else}
		<div class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
						<th class="text-left py-2 pr-4">이름</th>
						<th class="text-left py-2 pr-4">설명</th>
						<th class="text-left py-2 pr-4">상태</th>
						<th class="text-left py-2 pr-4">ID</th>
						<th class="text-left py-2">생성일</th>
					</tr>
				</thead>
				<tbody>
					{#each projects as p (p.id)}
						<tr class="border-b border-gray-800/50 text-xs hover:bg-gray-800/50 transition-colors cursor-pointer" onclick={() => { editProject = p; editName = p.name; editDesc = p.description; editEnabled = p.enabled; editError = ''; }}>
							<td class="py-2 pr-4 text-white">{p.name}</td>
							<td class="py-2 pr-4 text-gray-400">{p.description || '-'}</td>
							<td class="py-2 pr-4"><span class="px-1.5 py-0.5 rounded text-xs font-medium {p.enabled ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}">{p.enabled ? '활성' : '비활성'}</span></td>
							<td class="py-2 pr-4 text-gray-500 font-mono text-xs">{p.id.slice(0, 8)}</td>
							<td class="py-2 text-gray-500">{p.created_at?.slice(0, 10) ?? '-'}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		<div class="flex items-center justify-between mt-3">
			<button disabled={markerStack.length === 0} onclick={() => { const prev = markerStack.slice(0, -1); markerStack = prev; load(prev[prev.length - 1]); }}
				class="px-3 py-1.5 text-xs rounded bg-gray-800 hover:bg-gray-700 text-gray-300 disabled:opacity-30">← 이전</button>
			<button disabled={!nextMarker} onclick={() => { if (nextMarker) { markerStack = [...markerStack, nextMarker]; load(nextMarker); } }}
				class="px-3 py-1.5 text-xs rounded bg-gray-800 hover:bg-gray-700 text-gray-300 disabled:opacity-30">다음 →</button>
		</div>
	{/if}
</div>

<!-- 생성 모달 -->
{#if showCreate}
	<div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onclick={() => { showCreate = false; createError = ''; }} role="dialog" onkeydown={(e) => e.key === 'Escape' && (showCreate = false)} tabindex="-1">
		<div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()}>
			<h2 class="text-lg font-semibold text-white mb-5">프로젝트 생성</h2>
			{#if createError}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{createError}</div>{/if}
			<div class="space-y-4">
				<div><label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름</label><input bind:value={form.name} type="text" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" /></div>
				<div><label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">설명</label><input bind:value={form.description} type="text" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" /></div>
				<div class="flex items-center gap-3">
					<button onclick={() => form.enabled = !form.enabled} class="relative w-11 h-6 rounded-full transition-colors {form.enabled ? 'bg-blue-600' : 'bg-gray-700'}"><span class="absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform {form.enabled ? 'translate-x-5' : ''}"></span></button>
					<span class="text-sm text-gray-300">{form.enabled ? '활성' : '비활성'}</span>
				</div>
			</div>
			<div class="flex justify-end gap-3 mt-6">
				<button onclick={() => { showCreate = false; createError = ''; }} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">취소</button>
				<button onclick={createProject} disabled={creating || !form.name} class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg disabled:opacity-30">{creating ? '생성 중...' : '생성'}</button>
			</div>
		</div>
	</div>
{/if}

<!-- 수정 모달 -->
{#if editProject}
	<div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onclick={() => { editProject = null; }} role="dialog" onkeydown={(e) => e.key === 'Escape' && (editProject = null)} tabindex="-1">
		<div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()}>
			<h2 class="text-lg font-semibold text-white mb-5">프로젝트 수정</h2>
			{#if editError}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{editError}</div>{/if}
			<div class="space-y-4">
				<div><label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름</label><input bind:value={editName} type="text" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" /></div>
				<div><label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">설명</label><input bind:value={editDesc} type="text" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" /></div>
				<div class="flex items-center gap-3">
					<button onclick={() => editEnabled = !editEnabled} class="relative w-11 h-6 rounded-full transition-colors {editEnabled ? 'bg-blue-600' : 'bg-gray-700'}"><span class="absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform {editEnabled ? 'translate-x-5' : ''}"></span></button>
					<span class="text-sm text-gray-300">{editEnabled ? '활성' : '비활성'}</span>
				</div>
				<div class="text-xs text-gray-500">ID: {editProject.id}</div>
			</div>
			<div class="flex justify-end gap-3 mt-6">
				<button onclick={() => { editProject = null; }} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">취소</button>
				<button onclick={updateProject} disabled={updating} class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg disabled:opacity-30">{updating ? '수정 중...' : '수정'}</button>
			</div>
		</div>
	</div>
{/if}