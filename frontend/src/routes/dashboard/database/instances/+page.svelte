<script lang="ts">
	import { untrack } from 'svelte';
	import { pushState } from '$app/navigation';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import StatusChip from '$lib/components/ui/StatusChip.svelte';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import DbCreatePanel from '$lib/components/database/DbCreatePanel.svelte';
	import SlidePanel from '$lib/components/SlidePanel.svelte';
	import DbInstanceDetailPanel from '$lib/components/database/DbInstanceDetailPanel.svelte';
	import type { DbInstance } from '$lib/types/resources';

	let instances = $state<DbInstance[]>([]);
	let loading = $state(true);
	let refreshing = $state(false);
	let deleting = $state<string | null>(null);
	let restarting = $state<string | null>(null);

	// 생성 패널
	let showCreatePanel = $state(false);

	// 상세 패널
	let selectedInstanceId = $state<string | null>(null);

	function openPanel(id: string) {
		selectedInstanceId = id;
		pushState(`/dashboard/database/instances/${id}`, { instanceId: id });
	}

	function closePanel() {
		selectedInstanceId = null;
		pushState('/dashboard/database/instances', {});
	}

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);


	async function load() {
		if (instances.length === 0) loading = true;
		else refreshing = true;
		try {
			instances = await api.get<DbInstance[]>('/api/database-instances', token, projectId);
		} catch {
			instances = [];
		} finally {
			loading = false;
			refreshing = false;
		}
	}

	async function forceRefresh() {
		refreshing = true;
		try {
			instances = await api.get<DbInstance[]>('/api/database-instances', token, projectId, { refresh: true });
		} catch {
			instances = [];
		} finally {
			refreshing = false;
		}
	}


	async function deleteInstance(id: string, name: string) {
		if (!confirm(`DB 인스턴스 "${name || id.slice(0, 8)}"를 삭제하시겠습니까?`)) return;
		deleting = id;
		try {
			await api.delete(`/api/database-instances/${id}`, token, projectId);
			await load();
		} catch (e) {
			alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			deleting = null;
		}
	}

	async function restartInstance(id: string, name: string) {
		if (!confirm(`DB 인스턴스 "${name || id.slice(0, 8)}"를 재시작하시겠습니까?`)) return;
		restarting = id;
		try {
			await api.post(`/api/database-instances/${id}/restart`, {}, token, projectId);
			await load();
		} catch (e) {
			alert('재시작 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			restarting = null;
		}
	}

	const ar = createAutoRefresh(() => load(), {
		storageKey: 'dashboard-database-instances',
		defaultActive: true,
		defaultInterval: 15,
		intervalOptions: [10, 15, 30, 60],
	});

	$effect(() => {
		const pid = $auth.projectId;
		if (!pid) return;
		instances = [];
		untrack(() => load());
	});
</script>

<DbCreatePanel bind:open={showCreatePanel} onCreated={load} />

{#if selectedInstanceId}
	<SlidePanel onClose={closePanel} width="w-full md:w-[70vw] max-w-4xl">
		<DbInstanceDetailPanel
			instanceId={selectedInstanceId}
			token={$auth.token ?? undefined}
			projectId={$auth.projectId ?? undefined}
			onClose={closePanel}
			onDeleted={() => { closePanel(); load(); }}
		/>
	</SlidePanel>
{/if}


<div class="p-4 md:p-8 max-w-7xl mx-auto">
	<PageHeader breadcrumb="DATABASE / INSTANCES" title="DB 인스턴스">
		{#snippet actions()}
			<AutoRefreshControl
				bind:active={ar.active}
				bind:intervalSeconds={ar.intervalSeconds}
				intervalOptions={ar.intervalOptions}
				refreshing={refreshing || loading}
				onManualRefresh={forceRefresh}
			/>
			<button
				onclick={() => (showCreatePanel = true)}
				class="text-xs text-white bg-amber-600 hover:bg-amber-500 transition-colors px-3 py-1.5 rounded border border-amber-500"
			>+ 인스턴스 생성</button>
		{/snippet}
	</PageHeader>

	{#if loading}
		<LoadingSkeleton variant="table" rows={5} />
	{:else if instances.length === 0}
		<div class="text-gray-600 text-sm">DB 인스턴스가 없습니다</div>
	{:else}
		<div class="overflow-x-auto" class:opacity-60={refreshing} class:pointer-events-none={refreshing}>
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
						<th class="text-left py-3 px-4 font-medium">이름</th>
						<th class="text-left py-3 px-4 font-medium">상태</th>
						<th class="text-left py-3 px-4 font-medium">Datastore</th>
						<th class="text-left py-3 px-4 font-medium">크기 (GB)</th>
						<th class="text-left py-3 px-4 font-medium">생성일</th>
						<th class="text-right py-3 px-4 font-medium">액션</th>
					</tr>
				</thead>
				<tbody>
					{#each instances as inst}
						<tr class="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
							<td class="py-3 px-4">
								<button onclick={() => openPanel(inst.id)} class="text-amber-400 hover:text-amber-300 font-medium text-left">
									{inst.name}
								</button>
							</td>
							<td class="py-3 px-4"><StatusChip status={inst.status} /></td>
							<td class="py-3 px-4 text-gray-300">{inst.datastore?.type ?? '-'} {inst.datastore?.version ?? ''}</td>
							<td class="py-3 px-4 text-gray-300">{inst.size || '-'}</td>
							<td class="py-3 px-4 text-gray-500 text-xs">{inst.created_at ? inst.created_at.slice(0, 10) : '-'}</td>
							<td class="py-3 px-4 text-right">
								<div class="flex justify-end gap-1">
									<button
										onclick={() => restartInstance(inst.id, inst.name)}
										disabled={restarting === inst.id}
										class="text-blue-400 hover:text-blue-300 disabled:text-gray-600 text-xs px-2 py-1 rounded border border-blue-900 hover:border-blue-700 disabled:border-gray-700 transition-colors"
									>{restarting === inst.id ? '...' : '재시작'}</button>
									<button
										onclick={(e) => { e.stopPropagation(); deleteInstance(inst.id, inst.name); }}
										disabled={deleting === inst.id}
										class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-1 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors"
									>{deleting === inst.id ? '...' : '삭제'}</button>
								</div>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>
