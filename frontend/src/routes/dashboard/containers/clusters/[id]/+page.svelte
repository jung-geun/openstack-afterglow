<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { auth } from '$lib/stores/auth';
  import { api, ApiError } from '$lib/api/client';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
  import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
  import type { Cluster, StackResource, StackEvent } from '$lib/types/cluster';
  import ClusterHeader from '$lib/components/dashboard/containers/clusters/id/ClusterHeader.svelte';
  import ClusterProgressBar from '$lib/components/dashboard/containers/clusters/id/ClusterProgressBar.svelte';
  import ClusterDetailGrid from '$lib/components/dashboard/containers/clusters/id/ClusterDetailGrid.svelte';
  import ClusterResourcesTab from '$lib/components/dashboard/containers/clusters/id/ClusterResourcesTab.svelte';
  import ClusterEventsTab from '$lib/components/dashboard/containers/clusters/id/ClusterEventsTab.svelte';

  type Tab = 'detail' | 'resources' | 'events';
  let activeTab = $state<Tab>('detail');

  let cluster = $state<Cluster | null>(null);
  let resources = $state<StackResource[]>([]);
  let events = $state<StackEvent[]>([]);
  let loading = $state(true);
  let resourcesLoading = $state(false);
  let eventsLoading = $state(false);
  let error = $state('');

  const clusterId = $derived($page.params.id);
  const token = $derived($auth.token ?? undefined);
  const projectId = $derived($auth.projectId ?? undefined);

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

  const ar = createAutoRefresh(() => { fetchResources(); fetchEvents(); }, {
    storageKey: 'dashboard-cluster-detail',
    defaultActive: true,
    defaultInterval: 10,
    intervalOptions: [10, 15, 30, 60]
  });

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
  });
</script>

<div class="p-4 md:p-8 max-w-5xl">
  {#if error}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>{/if}

  {#if loading}
    <div class="flex items-center gap-3 mb-6">
      <button onclick={() => goto('/dashboard/containers/clusters')} class="text-gray-400 hover:text-white transition-colors text-sm">← 클러스터 목록</button>
    </div>
    <LoadingSkeleton variant="detail" />
  {:else if cluster}
    <ClusterHeader
      {cluster}
      refreshing={loading || resourcesLoading || eventsLoading}
      {ar}
      onManualRefresh={() => { fetchCluster(); fetchResources(); fetchEvents(); }}
      onDelete={handleDelete}
    />

    <ClusterProgressBar {resources} {isInProgress} />

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
      <ClusterDetailGrid {cluster} />
    {:else if activeTab === 'resources'}
      <ClusterResourcesTab {resources} loading={resourcesLoading} onRefresh={fetchResources} />
    {:else if activeTab === 'events'}
      <ClusterEventsTab {events} loading={eventsLoading} onRefresh={fetchEvents} />
    {/if}
  {/if}
</div>
