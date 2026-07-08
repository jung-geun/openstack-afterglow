import { api, ApiError, getBaseUrl } from '$lib/api/client';
import { streamK3sProgress } from '$lib/api/k3sSseStream';
import { toast } from '$lib/stores/toast';
import { K3S_CREATE_STEPS } from '$lib/components/k3sSteps';
import { downloadBlobAs } from '$lib/utils/downloadBlob';
import type { K3sCluster } from '$lib/types/k3s';
import type { K3sProgressController } from '$lib/stores/k3sProgress.svelte';
import { confirmDialog } from '$lib/stores/confirm.svelte';

export interface K3sClusterListOpts {
  token: () => string | undefined;
  projectId: () => string | undefined;
  progress: K3sProgressController;
}

export function createK3sClusterListController(opts: K3sClusterListOpts) {
  let clusters = $state<K3sCluster[]>([]);
  let loading = $state(true);
  let refreshing = $state(false);
  let error = $state('');
  let deleting = $state<string | null>(null);
  let showDeleted = $state(false);
  let showModal = $state(false);
  let creating = $state(false);
  let createError = $state('');
  let inflight: AbortController | null = null;

  async function fetchClusters(fetchOpts?: { refresh?: boolean }) {
    inflight?.abort();
    const ctrl = new AbortController();
    inflight = ctrl;
    try {
      const qs = showDeleted ? '?include_deleted=true' : '';
      const data = await api.get<K3sCluster[]>(
        `/api/v1/k3s/clusters${qs}`,
        opts.token(), opts.projectId(),
        { ...(fetchOpts ?? {}), signal: ctrl.signal },
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

  async function createCluster(form: {
    name: string; agent_count: number; agent_flavor_id: string;
    network_id: string; key_name: string; os_type: string; template_id?: string;
    master_count: number; stampede_enabled?: boolean;
  }) {
    creating = true;
    createError = '';
    opts.progress.begin('create', '클러스터 생성 준비 중...');
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
        ...(form.stampede_enabled ? { stampede_enabled: true } : {}),
      };
      for await (const msg of streamK3sProgress('/api/v1/k3s/clusters/async', {
        method: 'POST', body, token: opts.token(), projectId: opts.projectId(),
      })) {
        opts.progress.apply(msg);
        if (msg.step !== prevStep && !opts.progress.visible && msg.step !== 'completed' && msg.step !== 'failed') {
          const stepLabel = K3S_CREATE_STEPS.find(s => s.id === msg.step)?.label ?? msg.step;
          toast.info(`${clusterName}: ${stepLabel} 진행 중...`);
        }
        prevStep = msg.step;
        if (msg.step === 'completed') {
          toast.success(`클러스터 "${clusterName || '클러스터'}" 생성 완료 (${opts.progress.elapsedSeconds}초)`);
        } else if (msg.step === 'failed') {
          toast.error(`클러스터 생성 실패: ${msg.error || '알 수 없는 오류'}`);
        }
      }
    } catch (e) {
      opts.progress.failWith(String(e));
    } finally {
      opts.progress.end();
      creating = false;
      await fetchClusters();
    }
  }

  async function deleteCluster(id: string, name: string) {
    if (!(await confirmDialog(`Drover 클러스터 "${name}"을 삭제하시겠습니까?\n모든 VM과 보안 그룹이 삭제됩니다.`))) return;
    deleting = id;
    opts.progress.begin('delete');
    try {
      for await (const msg of streamK3sProgress(`/api/v1/k3s/clusters/${id}/delete-async`, {
        method: 'POST', token: opts.token(), projectId: opts.projectId(),
      })) {
        opts.progress.apply(msg);
        if (msg.step === 'completed') toast.success(`클러스터 "${name}" 삭제 완료 (${opts.progress.elapsedSeconds}초)`);
        else if (msg.step === 'failed') toast.error(`클러스터 삭제 실패: ${msg.error || '알 수 없는 오류'}`);
      }
    } catch (e) {
      opts.progress.failWith(String(e));
      toast.error(`클러스터 삭제 실패: ${String(e)}`);
    } finally {
      opts.progress.end();
      deleting = null;
      await fetchClusters();
    }
  }

  async function downloadKubeconfig(id: string, name: string) {
    const baseUrl = getBaseUrl();
    const res = await fetch(`${baseUrl}/api/v1/k3s/clusters/${id}/kubeconfig`, {
      headers: {
        ...(opts.token() ? { 'Authorization': `Bearer ${opts.token()}` } : {}),
        ...(opts.projectId() ? { 'X-Project-Id': opts.projectId() } : {}),
      },
    });
    if (!res.ok) {
      if (res.status === 404) {
        toast.warning('kubeconfig가 아직 준비되지 않았습니다. 클러스터가 초기화 중입니다.');
      } else {
        toast.error(`다운로드 실패: HTTP ${res.status}`);
      }
      return;
    }
    downloadBlobAs(await res.blob(), `kubeconfig-${name}.yaml`);
  }

  async function forceRefresh() {
    refreshing = true;
    try {
      await fetchClusters({ refresh: true });
    } finally {
      refreshing = false;
    }
  }

  function toggleDeleted() {
    showDeleted = !showDeleted;
    fetchClusters();
  }

  return {
    get clusters() { return clusters; },
    get loading() { return loading; },
    set loading(v: boolean) { loading = v; },
    get refreshing() { return refreshing; },
    get error() { return error; },
    get deleting() { return deleting; },
    get showDeleted() { return showDeleted; },
    set showDeleted(v: boolean) { showDeleted = v; },
    get showModal() { return showModal; },
    set showModal(v: boolean) { showModal = v; },
    get creating() { return creating; },
    get createError() { return createError; },
    fetchClusters,
    createCluster,
    deleteCluster,
    downloadKubeconfig,
    forceRefresh,
    toggleDeleted,
  };
}
