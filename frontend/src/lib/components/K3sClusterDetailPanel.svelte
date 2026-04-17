<script lang="ts">
  import { auth } from '$lib/stores/auth';
  import { untrack } from 'svelte';
  import { goto } from '$app/navigation';
  import { api, ApiError, getBaseUrl } from '$lib/api/client';
  import InstanceDetailPanel from '$lib/components/InstanceDetailPanel.svelte';

  interface K3sCluster {
    id: string;
    name: string;
    status: string;
    status_reason: string | null;
    server_vm_id: string | null;
    agent_vm_ids: string[];
    agent_count: number;
    api_address: string | null;
    server_ip: string | null;
    network_id: string | null;
    key_name: string | null;
    k3s_version: string | null;
    created_at: string | null;
    updated_at: string | null;
  }

  interface K3sNodeHealth {
    name: string;
    role: string;
    ready: boolean;
    conditions: string[];
    kubelet_version: string | null;
  }

  interface K3sClusterHealth {
    cluster_id: string;
    cluster_name: string;
    status: string;
    api_server_reachable: boolean;
    healthz_ok: boolean;
    nodes: K3sNodeHealth[];
    checked_at: string;
    error: string | null;
    reachability: string;
  }

  interface Props {
    clusterId: string;
    onClose?: () => void;
    adminMode?: boolean;
  }

  let { clusterId, onClose, adminMode = false }: Props = $props();

  const statusColor: Record<string, string> = {
    ACTIVE:       'text-green-400 bg-green-900/30',
    CREATING:     'text-yellow-400 bg-yellow-900/30',
    PROVISIONING: 'text-blue-400 bg-blue-900/30',
    SCALING:      'text-cyan-400 bg-cyan-900/30',
    DELETING:     'text-orange-400 bg-orange-900/30',
    ERROR:        'text-red-400 bg-red-900/30',
  };

  const healthColor: Record<string, string> = {
    HEALTHY:     'text-green-400 bg-green-900/30 border-green-800',
    DEGRADED:    'text-yellow-400 bg-yellow-900/30 border-yellow-800',
    UNHEALTHY:   'text-red-400 bg-red-900/30 border-red-800',
    UNREACHABLE: 'text-gray-400 bg-gray-800/30 border-gray-700',
    UNKNOWN:     'text-gray-500 bg-gray-800/30 border-gray-700',
  };

  const token = $derived($auth.token ?? undefined);
  const projectId = $derived($auth.projectId ?? undefined);

  let cluster = $state<K3sCluster | null>(null);
  let health = $state<K3sClusterHealth | null>(null);
  let loading = $state(true);
  let error = $state('');
  let deleting = $state(false);
  let kubeconfigAvailable = $state(false);
  let checkingHealth = $state(false);

  // 인스턴스 상세 보기
  let viewingInstanceId = $state<string | null>(null);

  // 에이전트 스케일링
  let scalingTarget = $state<number | null>(null);
  let scaling = $state(false);
  let scaleError = $state('');
  let initialCheckDone = $state(false);

  const apiBase = $derived(adminMode ? '/api/admin/k3s-clusters' : '/api/k3s/clusters');

  async function fetchCluster() {
    if (!clusterId) return;
    try {
      cluster = await api.get<K3sCluster>(`${apiBase}/${clusterId}`, token, projectId);
      if (scalingTarget === null && cluster) {
        scalingTarget = cluster.agent_count;
      }
      error = '';
    } catch (e) {
      error = e instanceof ApiError ? `조회 실패 (${e.status})` : '서버 오류';
    } finally {
      loading = false;
    }
  }

  async function fetchHealth() {
    if (!clusterId || !cluster || cluster.status !== 'ACTIVE') return;
    try {
      health = await api.get<K3sClusterHealth>(`/api/k3s/clusters/${clusterId}/health`, token, projectId);
    } catch {
      // 404는 아직 헬스 데이터 없음 — 무시
    }
  }

  async function triggerHealthCheck() {
    if (!clusterId || checkingHealth) return;
    checkingHealth = true;
    try {
      health = await api.post<K3sClusterHealth>(`/api/k3s/clusters/${clusterId}/health/check`, {}, token, projectId);
    } catch (e) {
      // rate limit(429) 등 — 무시
    } finally {
      checkingHealth = false;
    }
  }

  async function checkKubeconfig() {
    if (!clusterId || !cluster || cluster.status !== 'ACTIVE') return;
    try {
      const baseUrl = getBaseUrl();
      const res = await fetch(`${baseUrl}${apiBase}/${clusterId}/kubeconfig`, {
        method: 'HEAD',
        headers: {
          ...(token ? { 'X-Auth-Token': token } : {}),
          ...(projectId ? { 'X-Project-Id': projectId } : {}),
        },
      });
      kubeconfigAvailable = res.ok;
    } catch {
      kubeconfigAvailable = false;
    }
  }

  async function downloadKubeconfig() {
    if (!clusterId || !cluster) return;
    const baseUrl = getBaseUrl();
    const res = await fetch(`${baseUrl}${apiBase}/${clusterId}/kubeconfig`, {
      headers: {
        ...(token ? { 'X-Auth-Token': token } : {}),
        ...(projectId ? { 'X-Project-Id': projectId } : {}),
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
    if (!cluster || !confirm(`k3s 클러스터 "${cluster.name}"을 삭제하시겠습니까?`)) return;
    deleting = true;
    try {
      await api.delete(`${apiBase}/${clusterId}`, token, projectId);
      if (onClose) onClose();
      else goto('/dashboard/containers/k3s');
    } catch (e) {
      alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
      deleting = false;
    }
  }

  async function applyScale() {
    if (scalingTarget === null || !cluster) return;
    if (scalingTarget === cluster.agent_vm_ids.length && scalingTarget === cluster.agent_count) return;
    if (!confirm(`에이전트 수를 ${cluster.agent_vm_ids.length}개에서 ${scalingTarget}개로 변경하시겠습니까?`)) return;
    scaling = true;
    scaleError = '';
    try {
      await api.patch(`${apiBase}/${clusterId}/scale`, { agent_count: scalingTarget }, token, projectId);
      await fetchCluster();
    } catch (e) {
      scaleError = e instanceof ApiError ? e.message : String(e);
    } finally {
      scaling = false;
    }
  }

  $effect(() => {
    if (!$auth.projectId || !clusterId) return;
    loading = true;
    scalingTarget = null;
    initialCheckDone = false;
    untrack(() => fetchCluster());
    const interval = setInterval(() => untrack(() => {
      fetchCluster();
      fetchHealth();
    }), 5000);
    return () => clearInterval(interval);
  });

  // ACTIVE 진입 시 1회만 kubeconfig 가용성 확인 (폴링 시마다 재실행 방지)
  $effect(() => {
    if (cluster?.status === 'ACTIVE' && !initialCheckDone) {
      initialCheckDone = true;
      untrack(() => {
        checkKubeconfig();
        fetchHealth();
      });
    }
  });
</script>

<div class="relative h-full">
<!-- 인스턴스 상세 보기 레이어 -->
{#if viewingInstanceId}
  <div class="absolute inset-0 z-10 bg-gray-950 overflow-y-auto">
    <div class="px-4 pt-4">
      <button
        onclick={() => viewingInstanceId = null}
        class="text-gray-400 hover:text-white text-sm transition-colors mb-2">
        ← 클러스터 상세
      </button>
    </div>
    <InstanceDetailPanel instanceId={viewingInstanceId} onClose={() => viewingInstanceId = null} />
  </div>
{/if}

<div class="p-6">
  <!-- 헤더 -->
  <div class="mb-5 flex items-center justify-between">
    {#if onClose}
      <button onclick={onClose} class="text-gray-400 hover:text-gray-200 text-sm transition-colors">
        ✕ 닫기
      </button>
    {:else}
      <a href="/dashboard/containers/k3s" class="text-gray-400 hover:text-gray-200 text-sm transition-colors">
        ← k3s 클러스터
      </a>
    {/if}
  </div>

  {#if loading}
    <div class="animate-pulse space-y-4">
      <div class="h-8 bg-gray-800 rounded w-64"></div>
      <div class="h-40 bg-gray-800 rounded"></div>
    </div>
  {:else if error}
    <div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">{error}</div>
  {:else if cluster}
    <!-- 클러스터 헤더 -->
    <div class="flex items-start justify-between mb-5">
      <div>
        <h1 class="text-xl font-bold text-white">{cluster.name}</h1>
        <div class="flex items-center gap-2 mt-1.5">
          <span class="px-2 py-0.5 rounded text-xs font-medium {statusColor[cluster.status] ?? 'text-gray-400 bg-gray-800'}">
            {cluster.status}
          </span>
          {#if health}
            <span class="px-2 py-0.5 rounded border text-xs font-medium {healthColor[health.status] ?? 'text-gray-500 bg-gray-800 border-gray-700'}">
              {health.status}
            </span>
          {/if}
          {#if cluster.k3s_version}
            <span class="text-xs text-gray-500">{cluster.k3s_version}</span>
          {/if}
        </div>
        {#if cluster.status_reason}
          <p class="text-xs text-gray-500 mt-1">{cluster.status_reason}</p>
        {/if}
      </div>
      <div class="flex items-center gap-2">
        {#if cluster.status === 'CREATING' || cluster.status === 'PROVISIONING'}
          <div class="flex items-center gap-1.5 text-yellow-400 text-xs">
            <span class="animate-pulse">●</span>
            <span>초기화 중...</span>
          </div>
        {:else if cluster.status === 'ACTIVE'}
          <button
            onclick={triggerHealthCheck}
            disabled={checkingHealth}
            class="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-200 text-xs rounded-lg transition-colors disabled:opacity-50">
            {checkingHealth ? '확인 중...' : '헬스 체크'}
          </button>
          <button onclick={downloadKubeconfig}
            class="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium rounded-lg transition-colors">
            kubeconfig 다운로드
          </button>
        {/if}
        <button onclick={deleteCluster} disabled={deleting}
          class="px-3 py-1.5 bg-red-900/40 hover:bg-red-900/60 border border-red-800 text-red-400 text-xs rounded-lg transition-colors disabled:opacity-50">
          {deleting ? '삭제 중...' : '클러스터 삭제'}
        </button>
      </div>
    </div>

    <!-- 정보 카드 2열 -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
      <div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
        <h3 class="text-xs text-gray-500 uppercase tracking-wide mb-3">클러스터 정보</h3>
        <dl class="space-y-1.5 text-sm">
          <div class="flex justify-between">
            <dt class="text-gray-400 text-xs">ID</dt>
            <dd class="font-mono text-xs text-gray-300">{cluster.id.slice(0, 12)}...</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-gray-400 text-xs">API 주소</dt>
            <dd class="text-gray-300 font-mono text-xs">{cluster.api_address || '-'}</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-gray-400 text-xs">서버 IP</dt>
            <dd class="text-gray-300 font-mono text-xs">{cluster.server_ip || '-'}</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-gray-400 text-xs">키페어</dt>
            <dd class="text-gray-300 text-xs">{cluster.key_name || '-'}</dd>
          </div>
          {#if health}
            <div class="flex justify-between">
              <dt class="text-gray-400 text-xs">API 서버</dt>
              <dd class="text-xs {health.api_server_reachable ? 'text-green-400' : 'text-red-400'}">
                {health.api_server_reachable ? '접근 가능' : '접근 불가'}
              </dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-gray-400 text-xs">healthz</dt>
              <dd class="text-xs {health.healthz_ok ? 'text-green-400' : 'text-red-400'}">
                {health.healthz_ok ? 'OK' : 'FAIL'}
              </dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-gray-400 text-xs">체크 시각</dt>
              <dd class="text-gray-400 text-xs">{new Date(health.checked_at).toLocaleTimeString('ko-KR')}</dd>
            </div>
          {/if}
        </dl>
      </div>

      <div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
        <h3 class="text-xs text-gray-500 uppercase tracking-wide mb-3">노드 현황</h3>
        {#if health && health.nodes.length > 0}
          <div class="space-y-2">
            {#each health.nodes as node}
              <div class="flex items-center justify-between py-1.5 border-b border-gray-800 last:border-0">
                <div class="flex items-center gap-2">
                  <span class="w-2 h-2 rounded-full {node.ready ? 'bg-green-400' : 'bg-red-400'}"></span>
                  <span class="text-xs text-gray-300 font-mono">{node.name}</span>
                  <span class="text-xs px-1.5 py-0.5 rounded {node.role === 'server' ? 'bg-purple-900/40 text-purple-400 border border-purple-800' : 'bg-blue-900/40 text-blue-400 border border-blue-800'}">
                    {node.role}
                  </span>
                </div>
                <div class="text-right">
                  <span class="text-xs {node.ready ? 'text-green-400' : 'text-red-400'}">
                    {node.ready ? 'Ready' : 'NotReady'}
                  </span>
                  {#if node.kubelet_version}
                    <div class="text-xs text-gray-600 font-mono">{node.kubelet_version}</div>
                  {/if}
                </div>
              </div>
            {/each}
          </div>
        {:else}
          <dl class="space-y-1.5 text-sm">
            <div class="flex justify-between">
              <dt class="text-gray-400 text-xs">서버(control plane)</dt>
              <dd class="text-gray-300 text-xs">1</dd>
            </div>
            <div class="flex justify-between items-center">
              <dt class="text-gray-400 text-xs">에이전트(worker)</dt>
              <dd class="flex items-center gap-1.5">
                {#if cluster.status === 'ACTIVE'}
                  <button
                    onclick={() => scalingTarget = Math.max(0, (scalingTarget ?? cluster!.agent_count) - 1)}
                    class="w-5 h-5 flex items-center justify-center bg-gray-700 hover:bg-gray-600 text-white rounded text-xs transition-colors">−</button>
                  <span class="text-gray-300 text-xs min-w-[2rem] text-center">
                    {cluster.agent_vm_ids.length} / {scalingTarget ?? cluster.agent_count}
                  </span>
                  <button
                    onclick={() => scalingTarget = Math.min(10, (scalingTarget ?? cluster!.agent_count) + 1)}
                    class="w-5 h-5 flex items-center justify-center bg-gray-700 hover:bg-gray-600 text-white rounded text-xs transition-colors">+</button>
                  {#if scalingTarget !== null && scalingTarget !== cluster.agent_count}
                    <button
                      onclick={applyScale}
                      disabled={scaling}
                      class="px-2 py-0.5 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded transition-colors disabled:opacity-50 ml-1">
                      {scaling ? '...' : '적용'}
                    </button>
                  {/if}
                {:else}
                  <span class="text-gray-300 text-xs">{cluster.agent_vm_ids.length} / {cluster.agent_count} 생성됨</span>
                {/if}
              </dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-gray-400 text-xs">생성일</dt>
              <dd class="text-gray-300 text-xs">{cluster.created_at ? cluster.created_at.split('T')[0] : '-'}</dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-gray-400 text-xs">마지막 업데이트</dt>
              <dd class="text-gray-300 text-xs">{cluster.updated_at ? cluster.updated_at.split('T')[0] : '-'}</dd>
            </div>
          </dl>
          {#if health === null && cluster.status === 'ACTIVE'}
            <p class="text-xs text-gray-600 mt-2">헬스 데이터 로드 중...</p>
          {/if}
          {#if scaleError}
            <p class="text-red-400 text-xs mt-2">{scaleError}</p>
          {/if}
        {/if}

        {#if health && health.nodes.length > 0}
          <!-- 에이전트 스케일링 컨트롤 (노드 헬스 표시 중에도) -->
          {#if cluster.status === 'ACTIVE'}
            <div class="flex items-center gap-1.5 mt-3 pt-3 border-t border-gray-800">
              <span class="text-gray-400 text-xs">에이전트:</span>
              <button
                onclick={() => scalingTarget = Math.max(0, (scalingTarget ?? cluster!.agent_count) - 1)}
                class="w-5 h-5 flex items-center justify-center bg-gray-700 hover:bg-gray-600 text-white rounded text-xs transition-colors">−</button>
              <span class="text-gray-300 text-xs min-w-[2rem] text-center">
                {cluster.agent_vm_ids.length} / {scalingTarget ?? cluster.agent_count}
              </span>
              <button
                onclick={() => scalingTarget = Math.min(10, (scalingTarget ?? cluster!.agent_count) + 1)}
                class="w-5 h-5 flex items-center justify-center bg-gray-700 hover:bg-gray-600 text-white rounded text-xs transition-colors">+</button>
              {#if scalingTarget !== null && scalingTarget !== cluster.agent_count}
                <button
                  onclick={applyScale}
                  disabled={scaling}
                  class="px-2 py-0.5 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded transition-colors disabled:opacity-50 ml-1">
                  {scaling ? '...' : '적용'}
                </button>
              {/if}
            </div>
            {#if scaleError}
              <p class="text-red-400 text-xs mt-1">{scaleError}</p>
            {/if}
          {/if}
        {/if}
      </div>
    </div>

    <!-- VM 목록 -->
    <div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <h3 class="text-xs text-gray-500 uppercase tracking-wide mb-3">VM 목록</h3>
      <div class="space-y-2">
        {#if cluster.server_vm_id}
          <div class="flex items-center justify-between py-2 border-b border-gray-800">
            <div class="flex items-center gap-2">
              <span class="text-xs bg-purple-900/40 text-purple-400 border border-purple-800 rounded px-1.5 py-0.5">서버</span>
              <span class="text-xs text-gray-300 font-mono">{cluster.server_vm_id.slice(0, 12)}...</span>
            </div>
            <button
              onclick={() => viewingInstanceId = cluster!.server_vm_id}
              class="text-xs text-blue-400 hover:text-blue-300 transition-colors">
              인스턴스 보기 →
            </button>
          </div>
        {/if}
        {#each cluster.agent_vm_ids as vmId, i}
          <div class="flex items-center justify-between py-2 {i < cluster.agent_vm_ids.length - 1 ? 'border-b border-gray-800' : ''}">
            <div class="flex items-center gap-2">
              <span class="text-xs bg-blue-900/40 text-blue-400 border border-blue-800 rounded px-1.5 py-0.5">에이전트 {i + 1}</span>
              <span class="text-xs text-gray-300 font-mono">{vmId.slice(0, 12)}...</span>
            </div>
            <button
              onclick={() => viewingInstanceId = vmId}
              class="text-xs text-blue-400 hover:text-blue-300 transition-colors">
              인스턴스 보기 →
            </button>
          </div>
        {/each}
        {#if !cluster.server_vm_id && cluster.agent_vm_ids.length === 0}
          <p class="text-xs text-gray-600 py-2">VM 정보가 없습니다.</p>
        {/if}
      </div>
    </div>
  {/if}
</div>
</div>
