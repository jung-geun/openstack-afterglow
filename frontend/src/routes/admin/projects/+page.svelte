<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import AdminProjectTable from '$lib/components/admin/projects/AdminProjectTable.svelte';
	import Pagination from '$lib/components/ui/Pagination.svelte';
	import AdminProjectCreateModal from '$lib/components/admin/projects/AdminProjectCreateModal.svelte';
	import AdminProjectEditModal from '$lib/components/admin/projects/AdminProjectEditModal.svelte';
	import AdminProjectDeleteModal from '$lib/components/admin/projects/AdminProjectDeleteModal.svelte';
	import AdminProjectAccessModal from '$lib/components/admin/projects/AdminProjectAccessModal.svelte';

	import type { Project } from '$lib/types/project';
	import type { PagedResponse } from '$lib/types/common';

	let projects = $state<Project[]>([]);
	let loading = $state(true);
	let refreshing = $state(false);
	let pageSize = $state(20);
	let markerStack = $state<string[]>([]);
	let nextMarker = $state<string | null>(null);

	let showCreate = $state(false);
	let editProject = $state<Project | null>(null);
	let deleteProject = $state<Project | null>(null);
	let accessProject = $state<Project | null>(null);

	let copiedId = $state<string | null>(null);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	function copyId(id: string) {
		navigator.clipboard.writeText(id).then(() => {
			copiedId = id;
			setTimeout(() => { copiedId = null; }, 1500);
		});
	}

	async function load(marker?: string) {
		if (projects.length === 0) loading = true;
		else refreshing = true;
		try {
			let url = `/api/v1/admin/projects?limit=${pageSize}`;
			if (marker) url += `&marker=${marker}`;
			const res = await api.get<PagedResponse<Project>>(url, token, projectId);
			projects = res.items; nextMarker = res.next_marker;
		} catch { projects = []; } finally { loading = false; refreshing = false; }
	}

	function autoRefreshLoad() { load(markerStack[markerStack.length - 1]); }

	const ar = createAutoRefresh(autoRefreshLoad, {
		storageKey: 'admin-projects',
		defaultActive: true,
		defaultInterval: 60,
		intervalOptions: [30, 60],
	});

	onMount(() => {
		if (window.matchMedia('(max-width: 767px)').matches) pageSize = 10;
		load();
	});
</script>

<div class="p-4 md:p-6 max-w-7xl mx-auto">
	<PageHeader breadcrumb="IDENTITY / PROJECTS" title="프로젝트">
		{#snippet actions()}
			<button
				onclick={() => { showCreate = true; }}
				class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg"
			>+ 생성</button>
			<AutoRefreshControl
				bind:active={ar.active}
				bind:intervalSeconds={ar.intervalSeconds}
				intervalOptions={ar.intervalOptions}
				refreshing={loading || refreshing}
				onManualRefresh={() => load()}
			/>
			<div class="flex items-center gap-1 text-xs text-gray-500 max-md:hidden">
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

	{#if loading}
		<LoadingSkeleton variant="table" rows={5} />
	{:else}
		<div class="bg-gray-900 border border-gray-800 rounded-2xl p-5" class:opacity-60={refreshing} class:pointer-events-none={refreshing}>
			<AdminProjectTable
				{projects}
				{copiedId}
				onCopyId={copyId}
				onEdit={(p) => (editProject = p)}
				onAccess={(p) => (accessProject = p)}
				onDelete={(p) => (deleteProject = p)}
			/>
		</div>
		<Pagination
			page={markerStack.length + 1}
			hasPrev={markerStack.length > 0}
			hasNext={!!nextMarker}
			onPrev={() => { const prev = markerStack.slice(0, -1); markerStack = prev; load(prev[prev.length - 1]); }}
			onNext={() => { if (nextMarker) { markerStack = [...markerStack, nextMarker]; load(nextMarker); } }}
		/>
	{/if}
</div>

<AdminProjectCreateModal bind:open={showCreate} onCreated={() => load()} />
<AdminProjectEditModal   project={editProject}   onClose={() => (editProject = null)}   onSuccess={() => load()} />
<AdminProjectDeleteModal project={deleteProject} onClose={() => (deleteProject = null)} onSuccess={() => load()} />
<AdminProjectAccessModal project={accessProject} onClose={() => (accessProject = null)} />
