<script lang="ts">
	import { confirmDialog } from '$lib/stores/confirm.svelte';
  import { untrack } from 'svelte';
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
  import { toast } from '$lib/stores/toast';

  type Tab = 'detail' | 'resources' | 'events';
  let activeTab = $state<Tab>('detail');

  let cluster = $state<Cluster | null>(null);
  let resources = $state<StackResource[]>([]);
  let events = $state<StackEvent[]>([]);
  let loading = $state(true);
  let resourcesLoading = $state(false);
  let eventsLoading = $state(false);
  let resourcesLoaded = $state(false);
  let eventsLoaded = $state(false);
  let error = $state('');
  let clusterGeneration = 0;
  let resourcesGeneration = 0;
  let eventsGeneration = 0;

  const clusterId = $derived($page.params.id);
  const token = $derived($auth.token ?? undefined);
  const projectId = $derived($auth.projectId ?? undefined);

  const isInProgress = $derived(
    cluster?.status?.includes('IN_PROGRESS') ?? false
  );

  async function fetchCluster() {
    const requestId = clusterId;
    const requestProjectId = projectId;
    const generation = ++clusterGeneration;
    try {
      const value = await api.get<Cluster>(`/api/v1/clusters/${requestId}`, token, requestProjectId);
      if (generation !== clusterGeneration || clusterId !== requestId || projectId !== requestProjectId) return;
      cluster = value;
      error = '';
    } catch (e) {
      if (generation === clusterGeneration && clusterId === requestId && projectId === requestProjectId) {
        error = e instanceof ApiError ? `조회 실패: ${e.message}` : '서버 오류';
      }
    } finally {
      if (generation === clusterGeneration && clusterId === requestId && projectId === requestProjectId) loading = false;
    }
  }

  async function fetchResources() {
    const requestId = clusterId;
    const requestProjectId = projectId;
    const generation = ++resourcesGeneration;
    resourcesLoading = true;
    try {
      const value = await api.get<StackResource[]>(`/api/v1/clusters/${requestId}/stack/resources`, token, requestProjectId);
      if (generation === resourcesGeneration && clusterId === requestId && projectId === requestProjectId) {
        resources = value;
        resourcesLoaded = true;
      }
    } catch {
      if (generation === resourcesGeneration && clusterId === requestId && projectId === requestProjectId) {
        resources = [];
        resourcesLoaded = false;
      }
    } finally {
      if (generation === resourcesGeneration && clusterId === requestId && projectId === requestProjectId) resourcesLoading = false;
    }
  }

  async function fetchEvents() {
    const requestId = clusterId;
    const requestProjectId = projectId;
    const generation = ++eventsGeneration;
    eventsLoading = true;
    try {
      const value = await api.get<StackEvent[]>(`/api/v1/clusters/${requestId}/stack/events`, token, requestProjectId);
      if (generation === eventsGeneration && clusterId === requestId && projectId === requestProjectId) {
        events = value;
        eventsLoaded = true;
      }
    } catch {
      if (generation === eventsGeneration && clusterId === requestId && projectId === requestProjectId) {
        events = [];
        eventsLoaded = false;
      }
    } finally {
      if (generation === eventsGeneration && clusterId === requestId && projectId === requestProjectId) eventsLoading = false;
    }
  }

  async function ensureTab(tab: Tab) {
    if (tab === 'resources' && !resourcesLoaded && !resourcesLoading) await fetchResources();
    if (tab === 'events' && !eventsLoaded && !eventsLoading) await fetchEvents();
  }

  async function switchTab(tab: Tab) {
    activeTab = tab;
    await ensureTab(tab);
  }

  async function refreshVisible() {
    const tasks: Promise<void>[] = [fetchCluster()];
    if (activeTab === 'resources') tasks.push(fetchResources());
    if (activeTab === 'events') tasks.push(fetchEvents());
    await Promise.allSettled(tasks);
  }

  const ar = createAutoRefresh(refreshVisible, {
    storageKey: 'dashboard-cluster-detail',
    defaultActive: true,
    defaultInterval: 10,
    intervalOptions: [10, 15, 30, 60],
    invokeOnMount: false,
  });

  async function handleDelete() {
    if (!cluster) return;
    if (!await confirmDialog(`클러스터 "${cluster.name}"을 삭제하시겠습니까?`)) return;
    try {
      await api.delete(`/api/v1/clusters/${clusterId}`, token, projectId);
      goto('/dashboard/containers/clusters');
    } catch (e) {
      toast.error('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
    }
  }

  $effect(() => {
    const requestId = clusterId;
    const requestProject = projectId;
    if (!requestId || !requestProject) return;
    loading = true;
    resources = [];
    events = [];
    activeTab = 'detail';
    untrack(() => void fetchCluster());
    resourcesLoaded = false;
    eventsLoaded = false;
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
      onManualRefresh={refreshVisible}
      onDelete={handleDelete}
    />

    <ClusterProgressBar {resources} {isInProgress} />

    <!-- 탭 -->
    <div class="flex gap-1 border-b border-gray-800 mb-6">
      {#each [['detail', '상세'], ['resources', '스택 리소스'], ['events', '스택 이벤트']] as [tab, label]}
        <button
          onclick={() => switchTab(tab as Tab)}
          onfocus={() => { if (cluster?.stack_id) void ensureTab(tab as Tab); }}
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
