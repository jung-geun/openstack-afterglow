<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { auth } from '$lib/stores/auth';
  import { api, ApiError } from '$lib/api/client';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';

  interface Cluster {
    id: string;
    name: string;
    status: string;
    status_reason: string | null;
    cluster_template_id: string | null;
    master_count: number;
    node_count: number;
    api_address: string | null;
    coe_version: string | null;
    keypair: string | null;
    create_timeout: number | null;
    created_at: string | null;
    updated_at: string | null;
  }

  const statusColor: Record<string, string> = {
    CREATE_COMPLETE:    'text-green-400 bg-green-900/30',
    CREATE_IN_PROGRESS: 'text-yellow-400 bg-yellow-900/30',
    CREATE_FAILED:      'text-red-400 bg-red-900/30',
    UPDATE_IN_PROGRESS: 'text-blue-400 bg-blue-900/30',
    UPDATE_COMPLETE:    'text-green-400 bg-green-900/30',
    DELETE_IN_PROGRESS: 'text-orange-400 bg-orange-900/30',
  };

  let cluster = $state<Cluster | null>(null);
  let loading = $state(true);
  let error = $state('');

  const clusterId = $derived($page.params.id);

  async function fetchCluster() {
    try {
      cluster = await api.get<Cluster>(`/api/clusters/${clusterId}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
      error = '';
    } catch (e) {
      error = e instanceof ApiError ? `조회 실패: ${e.message}` : '서버 오류';
    } finally {
      loading = false;
    }
  }

  async function handleDelete() {
    if (!cluster) return;
    if (!confirm(`클러스터 "${cluster.name}"을 삭제하시겠습니까?`)) return;
    try {
      await api.delete(`/api/clusters/${clusterId}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
      goto('/dashboard/containers/clusters');
    } catch (e) {
      alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
    }
  }

  onMount(fetchCluster);
</script>

<div class="p-8 max-w-3xl">
  <div class="flex items-center gap-3 mb-6">
    <button onclick={() => goto('/dashboard/containers/clusters')} class="text-gray-400 hover:text-white transition-colors">← 클러스터 목록</button>
  </div>

  {#if error}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>{/if}

  {#if loading}
    <LoadingSkeleton variant="detail" />
  {:else if cluster}
    <div class="flex items-start justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-white">{cluster.name}</h1>
        <p class="text-gray-500 text-sm mt-1 font-mono">{cluster.id}</p>
      </div>
      <button onclick={handleDelete} class="px-4 py-2 text-sm text-red-400 border border-red-800 hover:bg-red-900/30 rounded-lg transition-colors">삭제</button>
    </div>

    <div class="grid grid-cols-2 gap-4 mb-6">
      <div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
        <div class="text-xs text-gray-500 mb-1">상태</div>
        <span class="px-2 py-0.5 rounded text-xs font-medium {statusColor[cluster.status] ?? 'text-gray-400 bg-gray-800'}">{cluster.status}</span>
        {#if cluster.status_reason}
          <p class="text-xs text-gray-500 mt-2">{cluster.status_reason}</p>
        {/if}
      </div>
      <div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
        <div class="text-xs text-gray-500 mb-1">노드 구성</div>
        <div class="text-white text-sm">마스터 {cluster.master_count}개 / 워커 {cluster.node_count}개</div>
      </div>
      <div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
        <div class="text-xs text-gray-500 mb-1">API 주소</div>
        <div class="text-white text-xs font-mono">{cluster.api_address ?? '-'}</div>
      </div>
      <div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
        <div class="text-xs text-gray-500 mb-1">COE 버전</div>
        <div class="text-white text-sm">{cluster.coe_version ?? '-'}</div>
      </div>
      <div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
        <div class="text-xs text-gray-500 mb-1">키페어</div>
        <div class="text-white text-sm">{cluster.keypair ?? '-'}</div>
      </div>
      <div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
        <div class="text-xs text-gray-500 mb-1">생성일</div>
        <div class="text-white text-sm">{cluster.created_at?.slice(0, 19).replace('T', ' ') ?? '-'}</div>
      </div>
    </div>

    {#if cluster.api_address}
      <div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
        <div class="text-xs text-gray-500 mb-3">kubectl 설정</div>
        <pre class="bg-gray-950 rounded p-3 text-xs text-green-300 overflow-auto">openstack coe cluster config {cluster.name} --dir ~/.kube --force</pre>
      </div>
    {/if}
  {/if}
</div>
