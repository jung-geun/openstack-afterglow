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
    stack_id: string | null;
  }

  interface StackResource {
    resource_name: string;
    resource_type: string;
    physical_resource_id: string;
    resource_status: string;
    resource_status_reason: string | null;
    created_at: string | null;
  }

  interface StackEvent {
    resource_name: string;
    resource_status: string;
    resource_status_reason: string | null;
    event_time: string;
    logical_resource_id: string | null;
    physical_resource_id: string | null;
  }

  const statusColor: Record<string, string> = {
    CREATE_COMPLETE:    'text-green-400 bg-green-900/30',
    CREATE_IN_PROGRESS: 'text-yellow-400 bg-yellow-900/30',
    CREATE_FAILED:      'text-red-400 bg-red-900/30',
    UPDATE_IN_PROGRESS: 'text-blue-400 bg-blue-900/30',
    UPDATE_COMPLETE:    'text-green-400 bg-green-900/30',
    DELETE_IN_PROGRESS: 'text-orange-400 bg-orange-900/30',
    DELETE_FAILED:      'text-red-400 bg-red-900/30',
  };

  const resourceStatusColor = (s: string) => {
    if (s.endsWith('_COMPLETE')) return 'text-green-400';
    if (s.endsWith('_IN_PROGRESS')) return 'text-yellow-400';
    if (s.endsWith('_FAILED')) return 'text-red-400';
    return 'text-gray-400';
  };

  type Tab = 'detail' | 'resources' | 'events';
  let activeTab = $state<Tab>('detail');

  let cluster = $state<Cluster | null>(null);
  let resources = $state<StackResource[]>([]);
  let events = $state<StackEvent[]>([]);
  let loading = $state(true);
  let resourcesLoading = $state(false);
  let eventsLoading = $state(false);
  let error = $state('');
  let autoRefresh = $state(false);
  let refreshInterval: ReturnType<typeof setInterval> | null = null;

  const clusterId = $derived($page.params.id);
  const token = $derived($auth.token ?? undefined);
  const projectId = $derived($auth.projectId ?? undefined);

  // 프로그래스 계산
  const progressPct = $derived(() => {
    if (!resources.length) return 0;
    const complete = resources.filter(r => r.resource_status.endsWith('_COMPLETE')).length;
    return Math.round(complete / resources.length * 100);
  });

  const isInProgress = $derived(
    cluster?.status?.includes('IN_PROGRESS') ?? false
  );

  async function fetchCluster() {
    try {
      cluster = await api.get<Cluster>(`/api/clusters/${clusterId}`, token, projectId);
      error = '';
    } catch (e) {
      error = e instanceof ApiError ? `조회 실패: ${e.message}` : '서버 오류';
    } finally {
      loading = false;
    }
  }

  async function fetchResources() {
    resourcesLoading = true;
    try {
      resources = await api.get<StackResource[]>(`/api/clusters/${clusterId}/stack/resources`, token, projectId);
    } catch { resources = []; } finally { resourcesLoading = false; }
  }

  async function fetchEvents() {
    eventsLoading = true;
    try {
      events = await api.get<StackEvent[]>(`/api/clusters/${clusterId}/stack/events`, token, projectId);
    } catch { events = []; } finally { eventsLoading = false; }
  }

  async function switchTab(tab: Tab) {
    activeTab = tab;
    if (tab === 'resources' && resources.length === 0) await fetchResources();
    if (tab === 'events' && events.length === 0) await fetchEvents();
  }

  function toggleAutoRefresh() {
    autoRefresh = !autoRefresh;
    if (autoRefresh) {
      refreshInterval = setInterval(async () => {
        await fetchCluster();
        if (activeTab === 'resources') await fetchResources();
        if (activeTab === 'events') await fetchEvents();
      }, 10_000);
    } else if (refreshInterval) {
      clearInterval(refreshInterval);
      refreshInterval = null;
    }
  }

  async function handleDelete() {
    if (!cluster) return;
    if (!confirm(`클러스터 "${cluster.name}"을 삭제하시겠습니까?`)) return;
    try {
      await api.delete(`/api/clusters/${clusterId}`, token, projectId);
      goto('/dashboard/containers/clusters');
    } catch (e) {
      alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
    }
  }

  onMount(() => {
    fetchCluster();
    return () => { if (refreshInterval) clearInterval(refreshInterval); };
  });
</script>

<div class="p-8 max-w-5xl">
  <div class="flex items-center gap-3 mb-6">
    <button onclick={() => goto('/dashboard/containers/clusters')} class="text-gray-400 hover:text-white transition-colors text-sm">← 클러스터 목록</button>
  </div>

  {#if error}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>{/if}

  {#if loading}
    <LoadingSkeleton variant="detail" />
  {:else if cluster}
    <div class="flex items-start justify-between mb-4">
      <div>
        <h1 class="text-2xl font-bold text-white">{cluster.name}</h1>
        <p class="text-gray-500 text-sm mt-0.5 font-mono">ID: {cluster.id}</p>
        {#if cluster.stack_id}
          <p class="text-gray-600 text-xs mt-0.5 font-mono">Stack: {cluster.stack_id}</p>
        {/if}
      </div>
      <div class="flex items-center gap-2">
        {#if cluster.stack_id}
          <button
            onclick={toggleAutoRefresh}
            class="px-3 py-1.5 text-xs border rounded-lg transition-colors {autoRefresh ? 'border-blue-600 text-blue-400 bg-blue-900/20' : 'border-gray-700 text-gray-400 hover:border-gray-500'}"
          >
            {autoRefresh ? '⏸ 자동 새로고침' : '▶ 자동 새로고침 (10s)'}
          </button>
        {/if}
        <button onclick={handleDelete} class="px-4 py-1.5 text-sm text-red-400 border border-red-800 hover:bg-red-900/30 rounded-lg transition-colors">삭제</button>
      </div>
    </div>

    <!-- 진행 상태 바 (진행 중일 때만) -->
    {#if isInProgress && resources.length > 0}
      {@const pct = progressPct()}
      <div class="bg-gray-900 border border-gray-800 rounded-xl p-4 mb-4">
        <div class="flex items-center justify-between mb-2 text-sm">
          <span class="text-gray-400">배포 진행률</span>
          <span class="text-white font-medium">{pct}%</span>
        </div>
        <div class="w-full bg-gray-800 rounded-full h-2">
          <div class="bg-blue-500 h-2 rounded-full transition-all duration-500" style="width:{pct}%"></div>
        </div>
        <div class="text-xs text-gray-500 mt-1">
          {resources.filter(r => r.resource_status.endsWith('_COMPLETE')).length} / {resources.length} 리소스 완료
        </div>
      </div>
    {/if}

    <!-- 탭 -->
    <div class="flex gap-1 border-b border-gray-800 mb-6">
      {#each [['detail', '상세'], ['resources', '스택 리소스'], ['events', '스택 이벤트']] as [tab, label]}
        <button
          onclick={() => switchTab(tab as Tab)}
          class="px-4 py-2 text-sm transition-colors border-b-2 {activeTab === tab ? 'border-blue-500 text-white' : 'border-transparent text-gray-500 hover:text-gray-300'}"
          disabled={tab !== 'detail' && !cluster.stack_id}
        >{label}{tab !== 'detail' && !cluster.stack_id ? ' (없음)' : ''}</button>
      {/each}
    </div>

    {#if activeTab === 'detail'}
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

    {:else if activeTab === 'resources'}
      <div class="flex items-center justify-between mb-3">
        <div class="text-sm text-gray-400">{resources.length}개 리소스</div>
        <button onclick={fetchResources} class="text-xs text-gray-400 hover:text-white transition-colors">새로고침</button>
      </div>
      {#if resourcesLoading}
        <LoadingSkeleton variant="table" rows={5} />
      {:else if resources.length === 0}
        <div class="text-gray-600 text-sm">스택 리소스 정보를 불러올 수 없습니다</div>
      {:else}
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
                <th class="text-left py-2 pr-4">리소스 이름</th>
                <th class="text-left py-2 pr-4">타입</th>
                <th class="text-left py-2 pr-4">Physical ID</th>
                <th class="text-left py-2 pr-4">상태</th>
                <th class="text-left py-2">생성일</th>
              </tr>
            </thead>
            <tbody>
              {#each resources as r}
                <tr class="border-b border-gray-800/50 text-xs">
                  <td class="py-2 pr-4 text-white font-medium">{r.resource_name}</td>
                  <td class="py-2 pr-4 text-gray-500 font-mono text-xs">{r.resource_type}</td>
                  <td class="py-2 pr-4 text-gray-500 font-mono text-xs">{r.physical_resource_id?.slice(0, 12) || '-'}</td>
                  <td class="py-2 pr-4">
                    <span class="{resourceStatusColor(r.resource_status)} text-xs">{r.resource_status}</span>
                    {#if r.resource_status_reason}
                      <div class="text-gray-600 text-xs mt-0.5">{r.resource_status_reason}</div>
                    {/if}
                  </td>
                  <td class="py-2 text-gray-500">{r.created_at?.slice(0, 16).replace('T', ' ') ?? '-'}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}

    {:else if activeTab === 'events'}
      <div class="flex items-center justify-between mb-3">
        <div class="text-sm text-gray-400">{events.length}개 이벤트 (최신순)</div>
        <button onclick={fetchEvents} class="text-xs text-gray-400 hover:text-white transition-colors">새로고침</button>
      </div>
      {#if eventsLoading}
        <LoadingSkeleton variant="table" rows={8} />
      {:else if events.length === 0}
        <div class="text-gray-600 text-sm">스택 이벤트 정보를 불러올 수 없습니다</div>
      {:else}
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
                <th class="text-left py-2 pr-4">이벤트 시각</th>
                <th class="text-left py-2 pr-4">리소스</th>
                <th class="text-left py-2 pr-4">상태</th>
                <th class="text-left py-2">사유</th>
              </tr>
            </thead>
            <tbody>
              {#each events as e}
                <tr class="border-b border-gray-800/50 text-xs">
                  <td class="py-2 pr-4 text-gray-400 font-mono whitespace-nowrap">{e.event_time?.slice(0, 19).replace('T', ' ') ?? '-'}</td>
                  <td class="py-2 pr-4 text-white">{e.resource_name}</td>
                  <td class="py-2 pr-4">
                    <span class="{resourceStatusColor(e.resource_status)} font-medium">{e.resource_status}</span>
                  </td>
                  <td class="py-2 text-gray-500">{e.resource_status_reason ?? '-'}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    {/if}
  {/if}
</div>
