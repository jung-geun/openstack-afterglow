<script lang="ts">
  import { untrack } from 'svelte';
  import { auth } from '$lib/stores/auth';
  import { api, ApiError } from '$lib/api/client';
  import type { Router, Network } from '$lib/types/resources';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
  import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
  import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
  import SlidePanel from '$lib/components/SlidePanel.svelte';
  import RouterDetailPanel from '$lib/components/RouterDetailPanel.svelte';
  import PageHeader from '$lib/components/ui/PageHeader.svelte';
  import RouterCreateModal from '$lib/components/network/routers/RouterCreateModal.svelte';
  import RouterCardGrid from '$lib/components/network/routers/RouterCardGrid.svelte';
  import RouterEmptyState from '$lib/components/network/routers/RouterEmptyState.svelte';

  let selectedRouterId = $state<string | null>(null);

  function openRouterPanel(id: string) {
    selectedRouterId = id;
    history.pushState({ routerId: id }, '', `/dashboard/network/routers/${id}`);
  }
  function closeRouterPanel() {
    selectedRouterId = null;
    history.pushState({}, '', '/dashboard/network/routers');
  }

  let routers = $state<Router[]>([]);
  let externalNetworks = $state<Network[]>([]);
  let loading = $state(true);
  let refreshing = $state(false);
  let error = $state('');
  let showModal = $state(false);

  async function fetchRouters(opts?: { refresh?: boolean }) {
    try {
      routers = await api.get<Router[]>('/api/routers', $auth.token ?? undefined, $auth.projectId ?? undefined, opts);
      error = '';
    } catch (e) {
      error = e instanceof ApiError ? `조회 실패 (${e.status})` : '서버 오류';
    } finally {
      loading = false;
    }
  }

  async function forceRefresh() {
    refreshing = true;
    try { await fetchRouters({ refresh: true }); } finally { refreshing = false; }
  }

  async function fetchNetworks() {
    try {
      const nets = await api.get<Network[]>('/api/networks', $auth.token ?? undefined, $auth.projectId ?? undefined);
      externalNetworks = nets.filter(n => n.is_external);
    } catch { /* ignore */ }
  }

  async function createRouter(form: { name: string; external_network_id: string }): Promise<string | true> {
    try {
      const body: Record<string, unknown> = { name: form.name };
      if (form.external_network_id) body.external_network_id = form.external_network_id;
      await api.post('/api/routers', body, $auth.token ?? undefined, $auth.projectId ?? undefined);
      await fetchRouters();
      return true;
    } catch (e) {
      return e instanceof ApiError ? e.message : '생성 실패';
    }
  }

  function externalNetworkName(id: string | null): string {
    if (!id) return '';
    const net = externalNetworks.find(n => n.id === id);
    return net?.name || id.slice(0, 12) + '…';
  }

  const ar = createAutoRefresh(() => fetchRouters(), {
    storageKey: 'dashboard-network-routers',
    defaultActive: true,
    defaultInterval: 30,
    intervalOptions: [10, 15, 30, 60],
  });

  $effect(() => {
    const projectId = $auth.projectId;
    if (!projectId) return;
    loading = true;
    untrack(() => { fetchRouters(); fetchNetworks(); });
  });
</script>

<RouterCreateModal bind:open={showModal} {externalNetworks} onCreate={createRouter} />

<div class="p-4 md:p-8">
  <PageHeader breadcrumb="NETWORK / ROUTERS" title="라우터">
    {#snippet actions()}
      <AutoRefreshControl
        bind:active={ar.active}
        bind:intervalSeconds={ar.intervalSeconds}
        intervalOptions={ar.intervalOptions}
        refreshing={refreshing}
        onManualRefresh={forceRefresh}
      />
      <button onclick={() => showModal = true} class="bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">+ 라우터 생성</button>
    {/snippet}
  </PageHeader>

  {#if error}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>{/if}

  {#if loading}
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
      {#each Array(4) as _}
        <div class="animate-pulse h-44 bg-gray-900 border border-gray-800 rounded-2xl"></div>
      {/each}
    </div>
  {:else if routers.length === 0}
    <RouterEmptyState />
  {:else}
    <RouterCardGrid {routers} {externalNetworkName} onOpen={openRouterPanel} />
  {/if}
</div>

{#if selectedRouterId}
  <SlidePanel onClose={closeRouterPanel} width="w-full md:w-[60vw] max-w-2xl">
    <RouterDetailPanel
      routerId={selectedRouterId}
      onClose={closeRouterPanel}
      onDeleted={() => { fetchRouters(); closeRouterPanel(); }}
    />
  </SlidePanel>
{/if}
