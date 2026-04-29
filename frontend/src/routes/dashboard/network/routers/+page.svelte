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
  import StatusChip from '$lib/components/ui/StatusChip.svelte';
  import PageHeader from '$lib/components/ui/PageHeader.svelte';


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
  let creating = $state(false);
  let createError = $state('');
  let form = $state({ name: '', external_network_id: '' });

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
    try {
      await fetchRouters({ refresh: true });
    } finally {
      refreshing = false;
    }
  }

  async function fetchNetworks() {
    try {
      const nets = await api.get<Network[]>('/api/networks', $auth.token ?? undefined, $auth.projectId ?? undefined);
      externalNetworks = nets.filter(n => n.is_external);
    } catch { /* ignore */ }
  }

  async function createRouter() {
    if (!form.name.trim()) return;
    creating = true;
    createError = '';
    try {
      const body: Record<string, unknown> = { name: form.name };
      if (form.external_network_id) body.external_network_id = form.external_network_id;
      await api.post('/api/routers', body, $auth.token ?? undefined, $auth.projectId ?? undefined);
      showModal = false;
      form = { name: '', external_network_id: '' };
      await fetchRouters();
    } catch (e) {
      createError = e instanceof ApiError ? e.message : '생성 실패';
    } finally {
      creating = false;
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

{#if showModal}
  <div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onclick={() => { showModal = false; createError = ''; }} role="dialog" aria-modal="true" tabindex="-1" onkeydown={(e) => e.key === 'Escape' && (showModal = false)}>
    <div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()} role="none" onkeydown={(e) => e.stopPropagation()}>
      <h2 class="text-lg font-semibold text-white mb-5">라우터 생성</h2>
      <div class="space-y-4">
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름
            <input bind:value={form.name} type="text" placeholder="my-router" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
          </label>
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">외부 네트워크 (선택)
            <select bind:value={form.external_network_id} class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5">
              <option value="">외부 게이트웨이 없음</option>
              {#each externalNetworks as net}
                <option value={net.id}>{net.name || net.id.slice(0, 12)}</option>
              {/each}
            </select>
          </label>
        </div>
      </div>
      {#if createError}<div class="mt-4 text-red-400 text-xs bg-red-900/20 border border-red-800 rounded px-3 py-2">{createError}</div>{/if}
      <div class="flex justify-end gap-3 mt-6">
        <button onclick={() => { showModal = false; createError = ''; }} class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">취소</button>
        <button onclick={createRouter} disabled={creating} class="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors">{creating ? '생성 중...' : '생성'}</button>
      </div>
    </div>
  </div>
{/if}

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
    <div class="text-center py-20 text-gray-600">
      <div class="text-5xl mb-4">🔀</div>
      <p class="text-lg">라우터가 없습니다</p>
    </div>
  {:else}
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
      {#each routers as router (router.id)}
        <div
          class="bg-gray-900 border border-gray-800 rounded-2xl p-5 cursor-pointer hover:border-gray-600 transition-colors"
          onclick={() => openRouterPanel(router.id)}
          role="button"
          tabindex="0"
          onkeydown={(e) => e.key === 'Enter' && openRouterPanel(router.id)}
        >
          <!-- Header -->
          <div class="flex items-center gap-2.5 mb-3.5">
            <div class="w-10 h-10 rounded-[10px] bg-violet-500/15 border border-violet-500/30 text-violet-400 flex items-center justify-center shrink-0">
              <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"/>
                <line x1="2" y1="12" x2="22" y2="12"/>
                <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
              </svg>
            </div>
            <div class="flex-1 min-w-0">
              <div class="text-white text-[14px] font-semibold truncate">{router.name || router.id.slice(0, 12)}</div>
              <div class="text-[11px] text-gray-500 mt-0.5">SNAT {router.external_gateway_network_id ? '활성' : '비활성'}</div>
            </div>
            <StatusChip status={router.status} />
          </div>

          <!-- Gateway / subnet info -->
          <div class="flex flex-col gap-2 text-[13px]">
            <div class="flex items-center gap-3 p-2.5 bg-[#0B1220] border border-gray-800 rounded-lg">
              <div class="text-[11px] uppercase tracking-wider font-medium text-gray-500 w-16 shrink-0">외부</div>
              {#if router.external_gateway_network_id}
                <div class="text-amber-400 font-mono text-xs truncate">{externalNetworkName(router.external_gateway_network_id)}</div>
              {:else}
                <div class="text-gray-600 text-xs">없음</div>
              {/if}
            </div>
            <div class="flex items-start gap-3 p-2.5 bg-[#0B1220] border border-gray-800 rounded-lg">
              <div class="text-[11px] uppercase tracking-wider font-medium text-gray-500 w-16 pt-0.5 shrink-0">내부</div>
              <div class="flex-1 flex flex-wrap gap-1.5">
                {#if router.connected_subnet_ids.length === 0}
                  <span class="text-gray-600 text-xs">인터페이스 없음</span>
                {:else}
                  {#each router.connected_subnet_ids as subnetId}
                    <span class="px-1.5 py-0.5 bg-gray-800 border border-gray-700 rounded text-[10px] text-gray-400 font-mono">{subnetId.slice(0, 8)}…</span>
                  {/each}
                {/if}
              </div>
            </div>
          </div>
        </div>
      {/each}
    </div>
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
