<script lang="ts">
	import { untrack } from 'svelte';
	import { auth, authReady } from '$lib/stores/auth';
	import { api, ApiError, getBaseUrl } from '$lib/api/client';
	import { streamK3sProgress } from '$lib/api/k3sSseStream';
	import { toast } from '$lib/stores/toast';
	import { createK3sProgress } from '$lib/stores/k3sProgress.svelte';
	import K3sClusterDetailPanel from '$lib/components/K3sClusterDetailPanel.svelte';
	import SlidePanel from '$lib/components/SlidePanel.svelte';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import { createDroverClusterPanel } from '$lib/utils/droverClusterPanel.svelte';
	import { K3S_CREATE_STEPS, K3S_DELETE_STEPS } from '$lib/components/k3sSteps';
	import K3sCreateClusterModal from '$lib/components/dashboard/drover/K3sCreateClusterModal.svelte';
	import K3sProgressModal from '$lib/components/dashboard/drover/K3sProgressModal.svelte';
	import DroverHeader from '$lib/components/dashboard/drover/DroverHeader.svelte';
	import DroverClusterGrid from '$lib/components/dashboard/drover/DroverClusterGrid.svelte';
	import type { K3sCluster } from '$lib/types/k3s';

	const progress = createK3sProgress();
	const activeSteps = $derived(progress.mode === 'delete' ? K3S_DELETE_STEPS : K3S_CREATE_STEPS);
	const panel = createDroverClusterPanel();

	let clusters = $state<K3sCluster[]>([]);
	let loading = $state(true);
	let refreshing = $state(false);
	let error = $state('');
	let deleting = $state<string | null>(null);
	let showDeleted = $state(false);

	let showModal = $state(false);
	let creating = $state(false);
	let createError = $state('');

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	let inflight: AbortController | null = null;

	async function fetchClusters(opts?: { refresh?: boolean }) {
		inflight?.abort();
		const ctrl = new AbortController();
		inflight = ctrl;
		try {
			const qs = showDeleted ? '?include_deleted=true' : '';
			const data = await api.get<K3sCluster[]>(
				`/api/k3s/clusters${qs}`,
				token, projectId,
				{ ...(opts ?? {}), signal: ctrl.signal },
			);
			if (ctrl.signal.aborted) return;
			clusters = data;
			error = '';
		} catch (e) {
			if (ctrl.signal.aborted) return;
			if (e instanceof ApiError && e.status === 503) {
				error = 'k3s 서비스를 사용할 수 없습니다.';
			} else {
				error = e instanceof ApiError ? `조회 실패 (${e.status})` : '서버 오류';
			}
		} finally {
			if (inflight === ctrl) inflight = null;
			loading = false;
		}
	}

	async function createCluster(form: { name: string; agent_count: number; agent_flavor_id: string; network_id: string; key_name: string; os_type: string; template_id?: string }) {
		creating = true;
		createError = '';
		progress.begin('create', '클러스터 생성 준비 중...');
		const clusterName = form.name;
		let prevStep = '';
		try {
			const body = {
				name: form.name,
				agent_count: form.agent_count,
				os_type: form.os_type,
				...(form.agent_flavor_id ? { agent_flavor_id: form.agent_flavor_id } : {}),
				...(form.network_id ? { network_id: form.network_id } : {}),
				...(form.key_name ? { key_name: form.key_name } : {}),
				...(form.template_id ? { template_id: form.template_id } : {}),
			};
			for await (const msg of streamK3sProgress('/api/k3s/clusters/async', { method: 'POST', body, token, projectId })) {
				progress.apply(msg);
				if (msg.step !== prevStep && !progress.visible && msg.step !== 'completed' && msg.step !== 'failed') {
					const stepLabel = K3S_CREATE_STEPS.find(s => s.id === msg.step)?.label ?? msg.step;
					toast.info(`${clusterName}: ${stepLabel} 진행 중...`);
				}
				prevStep = msg.step;
				if (msg.step === 'completed') {
					toast.success(`클러스터 "${clusterName || '클러스터'}" 생성 완료 (${progress.elapsedSeconds}초)`);
				} else if (msg.step === 'failed') {
					toast.error(`클러스터 생성 실패: ${msg.error || '알 수 없는 오류'}`);
				}
			}
		} catch (e) {
			progress.failWith(String(e));
		} finally {
			progress.end();
			creating = false;
			await fetchClusters();
		}
	}

	async function deleteCluster(id: string, name: string) {
		if (!confirm(`Drover 클러스터 "${name}"을 삭제하시겠습니까?\n모든 VM과 보안 그룹이 삭제됩니다.`)) return;
		deleting = id;
		progress.begin('delete');
		try {
			for await (const msg of streamK3sProgress(`/api/k3s/clusters/${id}/delete-async`, { method: 'POST', token, projectId })) {
				progress.apply(msg);
				if (msg.step === 'completed') toast.success(`클러스터 "${name}" 삭제 완료 (${progress.elapsedSeconds}초)`);
				else if (msg.step === 'failed') toast.error(`클러스터 삭제 실패: ${msg.error || '알 수 없는 오류'}`);
			}
		} catch (e) {
			progress.failWith(String(e));
			toast.error(`클러스터 삭제 실패: ${String(e)}`);
		} finally {
			progress.end();
			deleting = null;
			await fetchClusters();
		}
	}

	async function downloadKubeconfig(id: string, name: string) {
		const baseUrl = getBaseUrl();
		const res = await fetch(`${baseUrl}/api/k3s/clusters/${id}/kubeconfig`, {
			headers: {
				...(token ? { 'Authorization': `Bearer ${token}` } : {}),
				...(projectId ? { 'X-Project-Id': projectId } : {}),
			},
		});
		if (!res.ok) {
			if (res.status === 404) {
				alert('kubeconfig가 아직 준비되지 않았습니다. 클러스터가 초기화 중입니다.');
			} else {
				alert(`다운로드 실패: HTTP ${res.status}`);
			}
			return;
		}
		const blob = await res.blob();
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = `kubeconfig-${name}.yaml`;
		a.click();
		URL.revokeObjectURL(url);
	}

	async function forceRefresh() {
		refreshing = true;
		try {
			await fetchClusters({ refresh: true });
		} finally {
			refreshing = false;
		}
	}

	const ar = createAutoRefresh(() => fetchClusters(), {
		storageKey: 'dashboard-drover',
		defaultActive: true,
		defaultInterval: 10,
		intervalOptions: [10, 15, 30, 60],
		invokeOnMount: false,
	});

	$effect(() => {
		const pid = $auth.projectId;
		const ready = $authReady;
		if (!pid || !ready) return;
		loading = true;
		untrack(() => fetchClusters());
	});
</script>

<K3sCreateClusterModal
	bind:open={showModal}
	token={token}
	projectId={projectId}
	createError={createError}
	creating={creating}
	onCreate={createCluster}
/>

{#if progress.visible}
	<K3sProgressModal
		controller={progress}
		activeSteps={activeSteps}
		onClose={() => { progress.visible = false; }}
		onViewCluster={(id) => { progress.visible = false; panel.open(id); }}
	/>
{/if}

{#if panel.selectedClusterId}
	<SlidePanel onClose={panel.close}>
		<K3sClusterDetailPanel clusterId={panel.selectedClusterId} onClose={panel.close} />
	</SlidePanel>
{/if}

<div class="p-4 md:p-8">
	<DroverHeader
		bind:showDeleted
		{ar}
		refreshing={refreshing || loading}
		onForceRefresh={forceRefresh}
		onOpenCreate={() => { showModal = true; }}
		onToggleDeleted={() => { showDeleted = !showDeleted; fetchClusters(); }}
	/>

	<p class="text-sm text-gray-500 mb-6">Nova VM + cloud-init으로 k3s Kubernetes 클러스터를 프로비저닝합니다.</p>

	{#if error}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>
	{/if}

	<DroverClusterGrid
		{clusters}
		{loading}
		deletingId={deleting}
		onSelect={panel.open}
		onDownloadKubeconfig={downloadKubeconfig}
		onDelete={deleteCluster}
		onOpenCreate={() => { showModal = true; }}
	/>
</div>
