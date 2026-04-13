<script lang="ts">
  import { page } from '$app/stores';
  import { auth } from '$lib/stores/auth';
  import { untrack } from 'svelte';
  import { goto } from '$app/navigation';
  import { api, ApiError } from '$lib/api/client';

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

  const statusColor: Record<string, string> = {
    ACTIVE:       'text-green-400 bg-green-900/30',
    CREATING:     'text-yellow-400 bg-yellow-900/30',
    PROVISIONING: 'text-blue-400 bg-blue-900/30',
    DELETING:     'text-orange-400 bg-orange-900/30',
    ERROR:        'text-red-400 bg-red-900/30',
  };

  const clusterId = $derived($page.params.id);
  const token = $derived($auth.token ?? undefined);
  const projectId = $derived($auth.projectId ?? undefined);

  let cluster = $state<K3sCluster | null>(null);
  let loading = $state(true);
  let error = $state('');
  let deleting = $state(false);
  let kubeconfigAvailable = $state(false);

  async function fetchCluster() {
    if (!clusterId) return;
    try {
      cluster = await api.get<K3sCluster>(`/api/k3s/clusters/${clusterId}`, token, projectId);
      error = '';
    } catch (e) {
      error = e instanceof ApiError ? `조회 실패 (${e.status})` : '서버 오류';
    } finally {
      loading = false;
    }
  }

  async function checkKubeconfig() {
    if (!clusterId || !cluster || cluster.status !== 'ACTIVE') return;
    try {
      const baseUrl = typeof window !== 'undefined'
        ? `${window.location.protocol}//${window.location.hostname}:8000`
        : 'http://backend:8000';
      const res = await fetch(`${baseUrl}/api/k3s/clusters/${clusterId}/kubeconfig`, {
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
    const baseUrl = typeof window !== 'undefined'
      ? `${window.location.protocol}//${window.location.hostname}:8000`
      : 'http://backend:8000';
    const res = await fetch(`${baseUrl}/api/k3s/clusters/${clusterId}/kubeconfig`, {
      headers: {
        ...(token ? { 'X-Auth-Token': token } : {}),
        ...(projectId ? { 'X-Project-Id': projectId } : {}),
      },
    });
    if (!res.ok) {
      if (res.status === 404) {
        alert('kubeconfig가 아직 준비되지 않았습니다.');
      } else {
        alert(`다운로드 실패: HTTP ${res.status}`);
      }
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
      await api.delete(`/api/k3s/clusters/${clusterId}`, token, projectId);
      goto('/dashboard/containers/k3s');
    } catch (e) {
      alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
      deleting = false;
    }
  }

  $effect(() => {
    if (!$auth.projectId || !clusterId) return;
    loading = true;
    untrack(() => fetchCluster());
    const interval = setInterval(() => {
      untrack(() => fetchCluster());
    }, 5000);
    return () => clearInterval(interval);
  });

  $effect(() => {
    if (cluster?.status === 'ACTIVE') {
      untrack(() => checkKubeconfig());
    }
  });
</script>

<div class="p-4 md:p-8">
  <!-- 헤더 -->
  <div class="flex items-center gap-3 mb-6">
    <a href="/dashboard/containers/k3s" class="text-gray-400 hover:text-white text-sm transition-colors">
      ← k3s 클러스터
    </a>
  </div>

  {#if loading}
    <div class="animate-pulse space-y-4">
      <div class="h-8 bg-gray-800 rounded w-64"></div>
      <div class="h-40 bg-gray-800 rounded"></div>
    </div>
  {:else if error}
    <div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">{error}</div>
  {:else if cluster}
    <div class="flex items-start justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-white">{cluster.name}</h1>
        <div class="flex items-center gap-2 mt-1.5">
          <span class="px-2 py-0.5 rounded text-xs font-medium {statusColor[cluster.status] ?? 'text-gray-400 bg-gray-800'}">
            {cluster.status}
          </span>
          {#if cluster.k3s_version}
            <span class="text-xs text-gray-500">{cluster.k3s_version}</span>
          {/if}
        </div>
        {#if cluster.status_reason}
          <p class="text-sm text-gray-500 mt-1">{cluster.status_reason}</p>
        {/if}
      </div>
      <div class="flex items-center gap-2">
        <!-- kubeconfig 다운로드 -->
        {#if cluster.status === 'CREATING' || cluster.status === 'PROVISIONING'}
          <div class="flex items-center gap-2 text-yellow-400 text-sm">
            <span class="animate-pulse">●</span>
            <span>k3s 초기화 중...</span>
          </div>
        {:else if cluster.status === 'ACTIVE'}
          <button onclick={downloadKubeconfig}
            class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-colors">
            kubeconfig 다운로드
          </button>
        {/if}
        <button onclick={deleteCluster} disabled={deleting}
          class="px-4 py-2 bg-red-900/40 hover:bg-red-900/60 border border-red-800 text-red-400 text-sm rounded-lg transition-colors disabled:opacity-50">
          {deleting ? '삭제 중...' : '클러스터 삭제'}
        </button>
      </div>
    </div>

    <!-- 클러스터 정보 카드 -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
      <div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
        <h3 class="text-xs text-gray-500 uppercase tracking-wide mb-3">클러스터 정보</h3>
        <dl class="space-y-2 text-sm">
          <div class="flex justify-between">
            <dt class="text-gray-400">ID</dt>
            <dd class="font-mono text-xs text-gray-300">{cluster.id.slice(0, 12)}...</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-gray-400">API 주소</dt>
            <dd class="text-gray-300 font-mono text-xs">{cluster.api_address || '-'}</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-gray-400">서버 IP</dt>
            <dd class="text-gray-300 font-mono text-xs">{cluster.server_ip || '-'}</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-gray-400">키페어</dt>
            <dd class="text-gray-300">{cluster.key_name || '-'}</dd>
          </div>
        </dl>
      </div>
      <div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
        <h3 class="text-xs text-gray-500 uppercase tracking-wide mb-3">노드 현황</h3>
        <dl class="space-y-2 text-sm">
          <div class="flex justify-between">
            <dt class="text-gray-400">서버(control plane)</dt>
            <dd class="text-gray-300">1</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-gray-400">에이전트(worker)</dt>
            <dd class="text-gray-300">{cluster.agent_vm_ids.length} / {cluster.agent_count} 생성됨</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-gray-400">생성일</dt>
            <dd class="text-gray-300">{cluster.created_at ? cluster.created_at.split('T')[0] : '-'}</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-gray-400">마지막 업데이트</dt>
            <dd class="text-gray-300">{cluster.updated_at ? cluster.updated_at.split('T')[0] : '-'}</dd>
          </div>
        </dl>
      </div>
    </div>

    <!-- VM 목록 -->
    <div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <h3 class="text-xs text-gray-500 uppercase tracking-wide mb-3">VM 목록</h3>
      <div class="space-y-2">
        <!-- 서버 VM -->
        {#if cluster.server_vm_id}
          <div class="flex items-center justify-between py-2 border-b border-gray-800">
            <div class="flex items-center gap-3">
              <span class="text-xs bg-purple-900/40 text-purple-400 border border-purple-800 rounded px-1.5 py-0.5">서버</span>
              <span class="text-sm text-gray-300 font-mono">{cluster.server_vm_id.slice(0, 12)}...</span>
            </div>
            <a href="/dashboard/compute/instances"
              class="text-xs text-blue-400 hover:text-blue-300 transition-colors">
              인스턴스 보기 →
            </a>
          </div>
        {/if}
        <!-- 에이전트 VM -->
        {#each cluster.agent_vm_ids as vmId, i}
          <div class="flex items-center justify-between py-2 {i < cluster.agent_vm_ids.length - 1 ? 'border-b border-gray-800' : ''}">
            <div class="flex items-center gap-3">
              <span class="text-xs bg-blue-900/40 text-blue-400 border border-blue-800 rounded px-1.5 py-0.5">에이전트 {i + 1}</span>
              <span class="text-sm text-gray-300 font-mono">{vmId.slice(0, 12)}...</span>
            </div>
            <a href="/dashboard/compute/instances"
              class="text-xs text-blue-400 hover:text-blue-300 transition-colors">
              인스턴스 보기 →
            </a>
          </div>
        {/each}
        {#if !cluster.server_vm_id && cluster.agent_vm_ids.length === 0}
          <p class="text-sm text-gray-600 py-2">VM 정보가 없습니다.</p>
        {/if}
      </div>
    </div>
  {/if}
</div>
