<script lang="ts">
	import { confirmDialog } from '$lib/stores/confirm.svelte';
	import { untrack } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import { createSwr } from '$lib/utils/swr.svelte';
	import { apiMut } from '$lib/api/mutations';
	import type { Instance } from '$lib/types/compute';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import InstanceDetailPanel from '$lib/components/InstanceDetailPanel.svelte';
	import SlidePanel from '$lib/components/SlidePanel.svelte';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import { openWizard } from '$lib/stores/wizard';
	import InstancesTable from '$lib/components/instance/list/InstancesTable.svelte';
	import { toast } from '$lib/stores/toast';
	import { isTransitional } from '$lib/utils/instanceStatus';
	import BulkSelectionOverlay from '$lib/components/ui/BulkSelectionOverlay.svelte';

	let instances = $state<Instance[]>([]);
	let loading = $state(true);
	let refreshing = $state(false);
	let error = $state('');
	let selectedInstanceId = $state<string | null>(null);
	let underutilized = $state<Record<string, boolean>>({});
	let selectedIds = $state(new Set<string>());
	let bulkActioning = $state(false);

	const { swrGet, swrSet } = createSwr(() => $auth.projectId);

	async function fetchInstances(opts?: { refresh?: boolean }) {
		const path = '/api/v1/instances';
		const cached = swrGet<Instance[]>(path);
		if (cached && instances.length === 0) instances = cached;
		try {
			instances = await api.get<Instance[]>(path, $auth.token ?? undefined, $auth.projectId ?? undefined, opts);
			swrSet(path, instances);
			error = '';
			// 리소스 사용량 배지 — 비차단 (실패해도 목록 미영향)
			void fetchSummaryBatch();
		} catch (e) {
			if (!cached) error = e instanceof ApiError ? `조회 실패 (${e.status}): ${(e as ApiError).message}` : '서버 오류';
		} finally {
			loading = false;
		}
	}

	async function fetchSummaryBatch() {
		const token = $auth.token;
		const projectId = $auth.projectId ?? undefined;
		if (!token) return;
		try {
			const resp = await api.get<{
				prometheus_available: boolean;
				instances: Record<string, { cpu_avg: number | null; mem_avg: number | null; underutilized: boolean }>;
			}>('/api/v1/instances/metrics-summary-batch', token, projectId);
			if (resp.prometheus_available) {
				const map: Record<string, boolean> = {};
				for (const [id, data] of Object.entries(resp.instances)) map[id] = data.underutilized;
				underutilized = map;
			}
		} catch {
			// Prometheus 미연결 등 — 배지 없음, 에러 미노출
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

	// 전이 중 인스턴스가 있으면 4초 가속, 모두 안정되면 해제
	$effect(() => {
		const hasTransitional = instances.some(i => isTransitional(i.status));
		ar.setBoost(hasTransitional ? 4 : null);
	});

	async function startInstance(id: string) {
		try {
			await apiMut('인스턴스 시작', () => api.post(`/api/v1/instances/${id}/start`, {}, $auth.token ?? undefined, $auth.projectId ?? undefined));
			ar.setBoost(4);
			await fetchInstances();
		} catch { /* error toast shown by apiMut */ }
	}

	async function stopInstance(id: string) {
		if (!await confirmDialog('인스턴스를 종료하시겠습니까?')) return;
		try {
			await apiMut('인스턴스 종료', () => api.post(`/api/v1/instances/${id}/stop`, {}, $auth.token ?? undefined, $auth.projectId ?? undefined));
			ar.setBoost(4);
			await fetchInstances();
		} catch { /* error toast shown by apiMut */ }
	}

	async function bulkAction(action: 'start' | 'stop' | 'delete') {
		const ids = [...selectedIds];
		if (ids.length === 0) return;

		const labels: Record<string, string> = { start: '시작', stop: '종료', delete: '삭제' };
		const verb = labels[action];

		if (action === 'stop' || action === 'delete') {
			const msg = action === 'delete'
				? `선택한 인스턴스 ${ids.length}개를 삭제하시겠습니까?\nManila share와 볼륨도 함께 삭제됩니다.`
				: `선택한 인스턴스 ${ids.length}개를 종료하시겠습니까?`;
			if (!await confirmDialog(msg)) return;
		}

		bulkActioning = true;
		try {
			const res = await api.post<{ results: { id: string; ok: boolean; error?: string }[] }>(
				'/api/v1/instances/bulk-action',
				{ action, instance_ids: ids },
				$auth.token ?? undefined,
				$auth.projectId ?? undefined,
			);
			const failed = res.results.filter(r => !r.ok);
			const succeeded = res.results.filter(r => r.ok).length;
			if (succeeded > 0) toast.success(`${succeeded}개 ${verb} 요청 완료`);
			if (failed.length > 0) toast.error(`${failed.length}개 처리 실패`);
			selectedIds = new Set();
			ar.setBoost(4);
			await fetchInstances();
		} catch {
			toast.error(`일괄 ${verb} 요청 실패`);
		} finally {
			bulkActioning = false;
		}
	}

	async function shelveInstance(id: string) {
		if (!await confirmDialog('인스턴스를 보관하시겠습니까? (SHELVED_OFFLOADED 상태로 전환됩니다)')) return;
		try {
			await apiMut('인스턴스 보관', () => api.post(`/api/v1/instances/${id}/shelve`, {}, $auth.token ?? undefined, $auth.projectId ?? undefined));
			await fetchInstances();
		} catch { /* error toast shown by apiMut */ }
	}

	async function unshelveInstance(id: string) {
		if (!await confirmDialog('인스턴스 보관을 해제하시겠습니까?')) return;
		try {
			await apiMut('인스턴스 보관 해제', () => api.post(`/api/v1/instances/${id}/unshelve`, {}, $auth.token ?? undefined, $auth.projectId ?? undefined));
			await fetchInstances();
		} catch { /* error toast shown by apiMut */ }
	}

	async function deleteInstance(id: string, name: string) {
		if (!await confirmDialog(`"${name}" 인스턴스를 삭제하시겠습니까?\nManila share와 볼륨도 함께 삭제됩니다.`)) return;
		try {
			await apiMut('인스턴스 삭제', () => api.delete(`/api/v1/instances/${id}`, $auth.token ?? undefined, $auth.projectId ?? undefined));
			await fetchInstances();
		} catch { /* error toast shown by apiMut */ }
	}

	async function openConsole(id: string) {
		try {
			const data = await api.get<{ url: string }>(`/api/v1/instances/${id}/console`, $auth.token ?? undefined, $auth.projectId ?? undefined);
			window.open(data.url, '_blank');
		} catch {
			toast.error('콘솔 URL을 가져올 수 없습니다');
		}
	}

	async function handleAction(kind: 'console' | 'shelve' | 'unshelve' | 'delete' | 'start' | 'stop', instance: Instance) {
		if (kind === 'console') await openConsole(instance.id);
		else if (kind === 'shelve') await shelveInstance(instance.id);
		else if (kind === 'unshelve') await unshelveInstance(instance.id);
		else if (kind === 'delete') await deleteInstance(instance.id, instance.name);
		else if (kind === 'start') await startInstance(instance.id);
		else if (kind === 'stop') await stopInstance(instance.id);
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

<div class="p-4 md:p-8 pb-28 md:pb-32">
	<PageHeader breadcrumb="COMPUTE / INSTANCES" title="인스턴스">
		{#snippet actions()}
			<AutoRefreshControl
				bind:active={ar.active}
				bind:intervalSeconds={ar.intervalSeconds}
				intervalOptions={ar.intervalOptions}
				refreshing={refreshing}
				onManualRefresh={forceRefresh}
			/>
			<button type="button" onclick={() => openWizard()} class="bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
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
			<button type="button" onclick={() => openWizard()} class="text-blue-400 hover:text-blue-300 text-sm mt-2 inline-block bg-transparent">첫 VM을 생성하세요 →</button>
		</div>
	{:else}
		<InstancesTable
			{instances}
			{underutilized}
			{selectedIds}
			onSelect={openInstancePanel}
			onAction={handleAction}
			onToggleSelect={(id) => {
				const next = new Set(selectedIds);
				if (next.has(id)) next.delete(id); else next.add(id);
				selectedIds = next;
			}}
			onToggleAll={() => {
				if (instances.every(i => selectedIds.has(i.id))) {
					selectedIds = new Set();
				} else {
					selectedIds = new Set(instances.map(i => i.id));
				}
			}}
		/>
	{/if}

<BulkSelectionOverlay
	count={selectedIds.size}
	busy={bulkActioning}
	onStart={() => bulkAction('start')}
	onStop={() => bulkAction('stop')}
	onDelete={() => bulkAction('delete')}
	onClear={() => { selectedIds = new Set(); }}
/>
</div>

{#if selectedInstanceId}
	<SlidePanel onClose={closeInstancePanel}>
		<InstanceDetailPanel instanceId={selectedInstanceId} onClose={closeInstancePanel} />
	</SlidePanel>
{/if}
