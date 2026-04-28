<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import SlidePanel from '$lib/components/SlidePanel.svelte';
	import ContainerDetailPanel from '$lib/components/ContainerDetailPanel.svelte';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import StatusChip from '$lib/components/ui/StatusChip.svelte';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';

	interface AdminContainer {
		uuid: string;
		name: string;
		status: string;
		image: string | null;
		cpu: number | null;
		memory: string | null;
		host: string | null;
		created_at: string | null;
		project_id: string | null;
	}

	let containers = $state<AdminContainer[]>([]);
	let loading = $state(true);
	let refreshing = $state(false);
	let selectedContainerId = $state<string | null>(null);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function load() {
		if (containers.length === 0) loading = true;
		else refreshing = true;
		try {
			containers = await api.get<AdminContainer[]>('/api/admin/all-containers', token, projectId);
		} catch {
			containers = [];
		} finally {
			loading = false;
			refreshing = false;
		}
	}

	const ar = createAutoRefresh(load, {
		storageKey: 'admin-containers',
		defaultActive: true,
		defaultInterval: 15,
		intervalOptions: [10, 15, 30, 60]
	});

	onMount(load);
</script>

<div class="p-4 md:p-8 max-w-6xl">
	<PageHeader breadcrumb="CONTAINERS" title="전체 컨테이너">
		{#snippet actions()}
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
		<LoadingSkeleton variant="table" rows={5} />
	{:else if containers.length === 0}
		<div class="text-gray-600 text-sm">컨테이너가 없습니다</div>
	{:else}
		<div class="overflow-x-auto" class:opacity-60={refreshing} class:pointer-events-none={refreshing}>
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
						<th class="text-left py-2 pr-4">이름</th>
						<th class="text-left py-2 pr-4">상태</th>
						<th class="text-left py-2 pr-4">이미지</th>
						<th class="text-left py-2 pr-4">CPU</th>
						<th class="text-left py-2 pr-4">메모리</th>
						<th class="text-left py-2 pr-4">호스트</th>
						<th class="text-left py-2">생성일</th>
					</tr>
				</thead>
				<tbody>
					{#each containers as c (c.uuid)}
						<tr
							class="border-b border-gray-800/50 text-xs hover:bg-gray-800/30 transition-colors cursor-pointer {selectedContainerId === c.uuid ? 'bg-gray-800/50' : ''}"
							onclick={() => (selectedContainerId = c.uuid)}
							onkeydown={(e) => e.key === 'Enter' && (selectedContainerId = c.uuid)}
							role="button"
							tabindex="0"
						>
							<td class="py-2 pr-4 text-white">{c.name || c.uuid.slice(0, 8)}</td>
							<td class="py-2 pr-4"><StatusChip status={c.status} /></td>
							<td class="py-2 pr-4 text-gray-400 font-mono text-xs">{c.image || '-'}</td>
							<td class="py-2 pr-4 text-gray-400">{c.cpu ?? '-'}</td>
							<td class="py-2 pr-4 text-gray-400">{c.memory || '-'}</td>
							<td class="py-2 pr-4 text-gray-400">{c.host || '-'}</td>
							<td class="py-2 text-gray-500">{c.created_at?.slice(0, 10) ?? '-'}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>

{#if selectedContainerId}
	<SlidePanel onClose={() => (selectedContainerId = null)} width="w-full md:w-[480px]">
		<ContainerDetailPanel
			containerId={selectedContainerId}
			onClose={() => (selectedContainerId = null)}
			adminMode={true}
			onRefresh={load}
		/>
	</SlidePanel>
{/if}