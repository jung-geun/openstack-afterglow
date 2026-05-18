<script lang="ts">
	import { untrack } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError, memoryCache } from '$lib/api/client';
	import { apiMut } from '$lib/api/mutations';
	import type { Instance } from '$lib/types/resources';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import InstanceDetailPanel from '$lib/components/InstanceDetailPanel.svelte';
	import SlidePanel from '$lib/components/SlidePanel.svelte';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import { openWizard } from '$lib/stores/wizard';
	import InstancesTable from '$lib/components/instance/list/InstancesTable.svelte';

	let instances = $state<Instance[]>([]);
	let loading = $state(true);
	let refreshing = $state(false);
	let error = $state('');
	let selectedInstanceId = $state<string | null>(null);

	function swrGet<T>(path: string): T | null {
		const key = `${path}:${$auth.projectId}`;
		const c = memoryCache.get(key);
		return c ? (c.data as T) : null;
	}
	function swrSet(path: string, data: unknown) {
		memoryCache.set(`${path}:${$auth.projectId}`, { data, timestamp: Date.now() });
	}

	async function fetchInstances(opts?: { refresh?: boolean }) {
		const path = '/api/instances';
		const cached = swrGet<Instance[]>(path);
		if (cached && instances.length === 0) instances = cached;
		try {
			instances = await api.get<Instance[]>(path, $auth.token ?? undefined, $auth.projectId ?? undefined, opts);
			swrSet(path, instances);
			error = '';
		} catch (e) {
			if (!cached) error = e instanceof ApiError ? `조회 실패 (${e.status}): ${(e as ApiError).message}` : '서버 오류';
		} finally {
			loading = false;
		}
	}

	async function forceRefresh() {
		refreshing = true;
		try {
			await fetchInstances({ refresh: true });
		} finally {
			refreshing = false;
		}
	}

	const ar = createAutoRefresh(() => fetchInstances(), {
		storageKey: 'dashboard-compute-instances',
		defaultActive: true,
		defaultInterval: 10,
		intervalOptions: [10, 15, 30, 60],
	});

	async function shelveInstance(id: string) {
		if (!confirm('인스턴스를 보관하시겠습니까? (SHELVED_OFFLOADED 상태로 전환됩니다)')) return;
		try {
			await apiMut('인스턴스 보관', () => api.post(`/api/instances/${id}/shelve`, {}, $auth.token ?? undefined, $auth.projectId ?? undefined));
			await fetchInstances();
		} catch { /* error toast shown by apiMut */ }
	}

	async function unshelveInstance(id: string) {
		if (!confirm('인스턴스 보관을 해제하시겠습니까?')) return;
		try {
			await apiMut('인스턴스 보관 해제', () => api.post(`/api/instances/${id}/unshelve`, {}, $auth.token ?? undefined, $auth.projectId ?? undefined));
			await fetchInstances();
		} catch { /* error toast shown by apiMut */ }
	}

	async function deleteInstance(id: string, name: string) {
		if (!confirm(`"${name}" 인스턴스를 삭제하시겠습니까?\nManila share와 볼륨도 함께 삭제됩니다.`)) return;
		try {
			await apiMut('인스턴스 삭제', () => api.delete(`/api/instances/${id}`, $auth.token ?? undefined, $auth.projectId ?? undefined));
			await fetchInstances();
		} catch { /* error toast shown by apiMut */ }
	}

	async function openConsole(id: string) {
		try {
			const data = await api.get<{ url: string }>(`/api/instances/${id}/console`, $auth.token ?? undefined, $auth.projectId ?? undefined);
			window.open(data.url, '_blank');
		} catch {
			alert('콘솔 URL을 가져올 수 없습니다');
		}
	}

	async function handleAction(kind: 'console' | 'shelve' | 'unshelve' | 'delete', instance: Instance) {
		if (kind === 'console') await openConsole(instance.id);
		else if (kind === 'shelve') await shelveInstance(instance.id);
		else if (kind === 'unshelve') await unshelveInstance(instance.id);
		else if (kind === 'delete') await deleteInstance(instance.id, instance.name);
	}

	function openInstancePanel(id: string) {
		selectedInstanceId = id;
		history.pushState({ instanceId: id }, '', `/dashboard/compute/instances/${id}`);
	}

	function closeInstancePanel() {
		selectedInstanceId = null;
		history.pushState({}, '', '/dashboard/compute/instances');
	}

	$effect(() => {
		const projectId = $auth.projectId;
		if (!projectId) return;
		loading = true;
		untrack(() => fetchInstances());
	});
</script>

<div class="p-4 md:p-8">
	<PageHeader breadcrumb="COMPUTE / INSTANCES" title="인스턴스">
		{#snippet actions()}
			<AutoRefreshControl
				bind:active={ar.active}
				bind:intervalSeconds={ar.intervalSeconds}
				intervalOptions={ar.intervalOptions}
				refreshing={refreshing}
				onManualRefresh={forceRefresh}
			/>
			<button type="button" onclick={openWizard} class="bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
				+ VM 생성
			</button>
		{/snippet}
	</PageHeader>

	{#if error}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>
	{/if}

	{#if loading}
		<LoadingSkeleton variant="table" rows={5} />
	{:else if instances.length === 0}
		<div class="text-center py-20 text-gray-600">
			<div class="text-5xl mb-4">☁️</div>
			<p class="text-lg">인스턴스가 없습니다</p>
			<button type="button" onclick={openWizard} class="text-blue-400 hover:text-blue-300 text-sm mt-2 inline-block bg-transparent">첫 VM을 생성하세요 →</button>
		</div>
	{:else}
		<InstancesTable {instances} onSelect={openInstancePanel} onAction={handleAction} />
	{/if}
</div>

{#if selectedInstanceId}
	<SlidePanel onClose={closeInstancePanel}>
		<InstanceDetailPanel instanceId={selectedInstanceId} onClose={closeInstancePanel} />
	</SlidePanel>
{/if}
