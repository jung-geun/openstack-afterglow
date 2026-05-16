import { getContext, setContext } from 'svelte';
import { api, ApiError, getBaseUrl } from '$lib/api/client';
import { streamK3sProgress } from '$lib/api/k3sSseStream';
import type { K3sCluster, K3sClusterHealth } from '$lib/types/resources';

export type { K3sCluster, K3sClusterHealth };

export const statusColor: Record<string, string> = {
  ACTIVE:       'text-green-400 bg-green-900/30',
  CREATING:     'text-yellow-400 bg-yellow-900/30',
  PROVISIONING: 'text-blue-400 bg-blue-900/30',
  SCALING:      'text-cyan-400 bg-cyan-900/30',
  DELETING:     'text-orange-400 bg-orange-900/30',
  ERROR:        'text-red-400 bg-red-900/30',
};

export const healthColor: Record<string, string> = {
  HEALTHY:     'text-green-400 bg-green-900/30 border-green-800',
  DEGRADED:    'text-yellow-400 bg-yellow-900/30 border-yellow-800',
  UNHEALTHY:   'text-red-400 bg-red-900/30 border-red-800',
  UNREACHABLE: 'text-gray-400 bg-gray-800/30 border-gray-700',
  UNKNOWN:     'text-gray-500 bg-gray-800/30 border-gray-700',
};

export interface K3sClusterDetailOpts {
  clusterId: () => string;
  token: () => string | undefined;
  projectId: () => string | undefined;
  adminMode: () => boolean;
  onClose?: () => void;
}

export function createK3sClusterDetailStore(opts: K3sClusterDetailOpts) {
  let cluster = $state<K3sCluster | null>(null);
  let health = $state<K3sClusterHealth | null>(null);
  let loading = $state(true);
  let error = $state('');
  let deleting = $state(false);
  let deleteProgress = $state<{ step: string; pct: number; msg: string; error: string } | null>(null);
  let kubeconfigAvailable = $state(false);
  let checkingHealth = $state(false);
  let viewingInstanceId = $state<string | null>(null);
  let scalingTarget = $state<number | null>(null);
  let scaling = $state(false);
  let scaleError = $state('');
  let initialCheckDone = $state(false);

  const apiBase = $derived(opts.adminMode() ? '/api/admin/k3s-clusters' : '/api/k3s/clusters');
  const isActive = $derived(cluster?.status === 'ACTIVE');

  async function loadCluster() {
    const id = opts.clusterId();
    if (!id) return;
    try {
      cluster = await api.get<K3sCluster>(`${apiBase}/${id}`, opts.token(), opts.projectId());
      if (scalingTarget === null && cluster) scalingTarget = cluster.agent_count;
      error = '';
    } catch (e) {
      error = e instanceof ApiError ? `조회 실패 (${e.status})` : '서버 오류';
    } finally {
      loading = false;
    }
  }

  async function loadHealth() {
    const id = opts.clusterId();
    if (!id || !cluster || cluster.status !== 'ACTIVE') return;
    try {
      health = await api.get<K3sClusterHealth>(`/api/k3s/clusters/${id}/health`, opts.token(), opts.projectId());
    } catch {
      // 404는 아직 헬스 데이터 없음 — 무시
    }
  }

  async function triggerHealthCheck() {
    const id = opts.clusterId();
    if (!id || checkingHealth) return;
    checkingHealth = true;
    try {
      health = await api.post<K3sClusterHealth>(`/api/k3s/clusters/${id}/health/check`, {}, opts.token(), opts.projectId());
    } catch {
      // rate limit(429) 등 — 무시
    } finally {
      checkingHealth = false;
    }
  }

  async function checkKubeconfig() {
    const id = opts.clusterId();
    if (!id || !cluster || cluster.status !== 'ACTIVE') return;
    try {
      const baseUrl = getBaseUrl();
      const res = await fetch(`${baseUrl}${apiBase}/${id}/kubeconfig`, {
        method: 'HEAD',
        headers: {
          ...(opts.token() ? { 'X-Auth-Token': opts.token()! } : {}),
          ...(opts.projectId() ? { 'X-Project-Id': opts.projectId()! } : {}),
        },
      });
      kubeconfigAvailable = res.ok;
    } catch {
      kubeconfigAvailable = false;
    }
  }

  async function downloadKubeconfig() {
    const id = opts.clusterId();
    if (!id || !cluster) return;
    const baseUrl = getBaseUrl();
    const res = await fetch(`${baseUrl}${apiBase}/${id}/kubeconfig`, {
      headers: {
        ...(opts.token() ? { 'X-Auth-Token': opts.token()! } : {}),
        ...(opts.projectId() ? { 'X-Project-Id': opts.projectId()! } : {}),
      },
    });
    if (!res.ok) {
      alert(res.status === 404 ? 'kubeconfig가 아직 준비되지 않았습니다.' : `다운로드 실패: HTTP ${res.status}`);
      return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `kubeconfig-${cluster.name}.yaml`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function deleteCluster() {
    const c = cluster;
    const id = opts.clusterId();
    if (!c || !confirm(`Drover 클러스터 "${c.name}"을 삭제하시겠습니까?`)) return;
    deleting = true;
    deleteProgress = { step: '', pct: 0, msg: '삭제 준비 중...', error: '' };
    try {
      for await (const msg of streamK3sProgress(
        `${apiBase}/${id}/delete-async`,
        { method: 'POST', token: opts.token(), projectId: opts.projectId() },
      )) {
        deleteProgress = { step: msg.step, pct: msg.progress, msg: msg.message, error: msg.error ?? '' };
        if (msg.step === 'completed') {
          opts.onClose?.();
          return;
        }
        if (msg.step === 'failed') {
          deleteProgress = { ...deleteProgress, error: msg.error ?? '알 수 없는 오류' };
          deleting = false;
          return;
        }
      }
    } catch (e) {
      deleteProgress = { step: 'failed', pct: 0, msg: '삭제 실패', error: String(e) };
      deleting = false;
    }
  }

  async function applyScale() {
    const c = cluster;
    const id = opts.clusterId();
    if (scalingTarget === null || !c) return;
    if (scalingTarget === c.agent_vm_ids.length && scalingTarget === c.agent_count) return;
    if (!confirm(`에이전트 수를 ${c.agent_vm_ids.length}개에서 ${scalingTarget}개로 변경하시겠습니까?`)) return;
    scaling = true;
    scaleError = '';
    try {
      await api.patch(`${apiBase}/${id}/scale`, { agent_count: scalingTarget }, opts.token(), opts.projectId());
      await loadCluster();
    } catch (e) {
      scaleError = e instanceof ApiError ? e.message : String(e);
    } finally {
      scaling = false;
    }
  }

  function incrementScale() {
    scalingTarget = Math.min(10, (scalingTarget ?? cluster?.agent_count ?? 0) + 1);
  }

  function decrementScale() {
    scalingTarget = Math.max(0, (scalingTarget ?? cluster?.agent_count ?? 0) - 1);
  }

  function reset() {
    cluster = null;
    health = null;
    loading = true;
    error = '';
    deleteProgress = null;
    deleting = false;
    scalingTarget = null;
    initialCheckDone = false;
    scaleError = '';
  }

  function setViewingInstance(id: string | null) {
    viewingInstanceId = id;
  }

  function clearViewingInstance() {
    viewingInstanceId = null;
  }

  return {
    get cluster() { return cluster; },
    get health() { return health; },
    get loading() { return loading; },
    get error() { return error; },
    get deleting() { return deleting; },
    get deleteProgress() { return deleteProgress; },
    get kubeconfigAvailable() { return kubeconfigAvailable; },
    get checkingHealth() { return checkingHealth; },
    get viewingInstanceId() { return viewingInstanceId; },
    get scalingTarget() { return scalingTarget; },
    set scalingTarget(v: number | null) { scalingTarget = v; },
    get scaling() { return scaling; },
    get scaleError() { return scaleError; },
    get initialCheckDone() { return initialCheckDone; },
    set initialCheckDone(v: boolean) { initialCheckDone = v; },
    get apiBase() { return apiBase; },
    get isActive() { return isActive; },
    loadCluster,
    loadHealth,
    triggerHealthCheck,
    checkKubeconfig,
    downloadKubeconfig,
    deleteCluster,
    applyScale,
    incrementScale,
    decrementScale,
    reset,
    setViewingInstance,
    clearViewingInstance,
  };
}

export type K3sClusterDetailStore = ReturnType<typeof createK3sClusterDetailStore>;

const K3S_CLUSTER_DETAIL_KEY = Symbol('k3s-cluster-detail');

export function provideK3sClusterDetail(store: K3sClusterDetailStore) {
  setContext(K3S_CLUSTER_DETAIL_KEY, store);
}

export function useK3sClusterDetail(): K3sClusterDetailStore {
  const store = getContext<K3sClusterDetailStore | undefined>(K3S_CLUSTER_DETAIL_KEY);
  if (!store) throw new Error('useK3sClusterDetail must be called within K3sClusterDetailPanel');
  return store;
}
