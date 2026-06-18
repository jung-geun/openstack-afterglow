<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import K3sClusterTemplateCard from '$lib/components/admin/drover/K3sClusterTemplateCard.svelte';
	import K3sClusterTemplateModal from '$lib/components/admin/drover/K3sClusterTemplateModal.svelte';
	import type { K3sClusterTemplate } from '$lib/types/k3s';
	import Modal from '$lib/components/ui/Modal.svelte';

	let templates = $state<K3sClusterTemplate[]>([]);
	let loading = $state(true);
	let refreshing = $state(false);
	let showCreate = $state(false);
	let editTarget = $state<K3sClusterTemplate | null>(null);
	let deleteTarget = $state<K3sClusterTemplate | null>(null);
	let deleteError = $state('');

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function load() {
		if (templates.length === 0) loading = true;
		else refreshing = true;
		try {
			templates = await api.get<K3sClusterTemplate[]>('/api/v1/admin/k3s-cluster-templates', token, projectId);
		} catch {
			templates = [];
		} finally {
			loading = false;
			refreshing = false;
		}
	}

	async function confirmDelete() {
		if (!deleteTarget) return;
		deleteError = '';
		try {
			await api.delete(`/api/v1/k3s/cluster-templates/${deleteTarget.id}`, token, projectId);
			deleteTarget = null;
			await load();
		} catch (e) {
			deleteError = e instanceof ApiError ? e.message : '삭제 실패';
		}
	}

	const ar = createAutoRefresh(load, {
		storageKey: 'admin-k3s-templates',
		defaultActive: false,
		defaultInterval: 60,
		intervalOptions: [30, 60],
	});

	onMount(load);
</script>

<div class="p-4 md:p-8 max-w-7xl mx-auto">
	<PageHeader breadcrumb="DROVER / CLUSTER TEMPLATES" title="클러스터 템플릿">
		{#snippet actions()}
			<button
				onclick={() => (showCreate = true)}
				class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg"
			>
				+ 생성
			</button>
			<AutoRefreshControl
				bind:active={ar.active}
				bind:intervalSeconds={ar.intervalSeconds}
				intervalOptions={ar.intervalOptions}
				refreshing={loading || refreshing}
				onManualRefresh={load}
			/>
		{/snippet}
	</PageHeader>

	{#if loading}
		<LoadingSkeleton variant="table" rows={3} />
	{:else}
		<div class:opacity-60={refreshing} class:pointer-events-none={refreshing}>
			{#if templates.length === 0}
				<div class="text-gray-500 text-sm py-12 text-center">등록된 클러스터 템플릿이 없습니다.</div>
			{:else}
				<div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
					{#each templates as t (t.id)}
						<K3sClusterTemplateCard
							template={t}
							onEdit={(tmpl) => (editTarget = tmpl)}
							onDelete={(tmpl) => { deleteTarget = tmpl; deleteError = ''; }}
						/>
					{/each}
				</div>
			{/if}
		</div>
	{/if}
</div>

{#if showCreate}
	<K3sClusterTemplateModal
		onClose={() => (showCreate = false)}
		onSaved={() => { showCreate = false; void load(); }}
	/>
{/if}

{#if editTarget}
	<K3sClusterTemplateModal
		template={editTarget}
		onClose={() => (editTarget = null)}
		onSaved={() => { editTarget = null; void load(); }}
	/>
{/if}

{#if deleteTarget}
	<Modal open={true} onClose={() => (deleteTarget = null)}>
		<div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-sm mx-4 shadow-2xl">
			<h2 class="text-lg font-semibold text-white mb-3">템플릿 삭제</h2>
			<p class="text-sm text-gray-300 mb-5">
				<strong class="text-white">{deleteTarget.name}</strong> 템플릿을 삭제합니다. 이미 생성된 클러스터에는 영향 없습니다.
			</p>
			{#if deleteError}
				<div class="mb-3 text-red-400 text-xs bg-red-900/20 border border-red-800 rounded px-3 py-2">{deleteError}</div>
			{/if}
			<div class="flex justify-end gap-3">
				<button onclick={() => (deleteTarget = null)} class="px-4 py-2 text-sm text-gray-400 hover:text-white">취소</button>
				<button onclick={confirmDelete} class="px-4 py-2 bg-red-700 hover:bg-red-600 text-white text-sm font-medium rounded-lg">삭제</button>
			</div>
		</div>
	</Modal>
{/if}
