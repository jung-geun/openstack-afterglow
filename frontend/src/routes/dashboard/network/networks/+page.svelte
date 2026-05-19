<script lang="ts">
	import { confirmDialog } from '$lib/stores/confirm.svelte';
  import { untrack } from 'svelte';
  import { auth } from '$lib/stores/auth';
  import { api, ApiError } from '$lib/api/client';
  import { createSwr } from '$lib/utils/swr.svelte';
  import { apiMut } from '$lib/api/mutations';
  import type { Network, FloatingIp } from '$lib/types/resources';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
  import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
  import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
  import SlidePanel from '$lib/components/SlidePanel.svelte';
  import NetworkDetailPanel from '$lib/components/NetworkDetailPanel.svelte';
  import PageHeader from '$lib/components/ui/PageHeader.svelte';
  import FloatingIpAllocateModal from '$lib/components/network/FloatingIpAllocateModal.svelte';
  import NetworkCreateModal from '$lib/components/dashboard/network/networks/NetworkCreateModal.svelte';
  import NetworksTableCard from '$lib/components/dashboard/network/networks/NetworksTableCard.svelte';
  import FloatingIpCard from '$lib/components/dashboard/network/networks/FloatingIpCard.svelte';
  import { toast } from '$lib/stores/toast';

  let networks = $state<Network[]>([]);
  let floatingIps = $state<FloatingIp[]>([]);
  let loading = $state(true);
  let refreshing = $state(false);
  let error = $state('');
  let deleting = $state<string | null>(null);
  let selectedNetworkId = $state<string | null>(null);
  let defaultNetworkId = $state<string | null>(null);
  let settingDefault = $state<string | null>(null);
  let showAllocateModal = $state(false);
  let showModal = $state(false);
  let creating = $state(false);
  let createError = $state('');

  $effect(() => { if (!showModal) createError = ''; });

  const tok = () => $auth.token ?? undefined;
  const pid = () => $auth.projectId ?? undefined;
  const { swrGet, swrSet } = createSwr(() => $auth.projectId);

  async function fetchNetworks(opts?: { refresh?: boolean }) {
    const path = '/api/networks';
    const cached = swrGet<Network[]>(path);
    if (cached && networks.length === 0) networks = cached;
    try {
      networks = await api.get<Network[]>(path, tok(), pid(), opts);
      swrSet(path, networks);
      error = '';
    } catch (e) {
      if (!cached) error = e instanceof ApiError ? `조회 실패 (${e.status})` : '서버 오류';
    } finally { loading = false; }
  }

  async function fetchDefaultNetwork() {
    try {
      const record = await api.get<{ network_id: string }>('/api/networks/default', tok(), pid());
      defaultNetworkId = record.network_id;
    } catch { defaultNetworkId = null; }
  }

  async function setAsDefault(networkId: string) {
    settingDefault = networkId;
    try {
      await api.put('/api/networks/default', { network_id: networkId }, tok(), pid());
      defaultNetworkId = networkId;
    } catch (e) {
      toast.error('기본 네트워크 설정 실패: ' + (e instanceof ApiError ? e.message : String(e)));
    } finally { settingDefault = null; }
  }

  async function fetchFloatingIps() {
    try {
      floatingIps = await api.get<FloatingIp[]>('/api/networks/floating-ips', tok(), pid());
    } catch { /* 오류 무시 */ }
  }

  async function forceRefresh() {
    refreshing = true;
    try { await Promise.all([fetchNetworks({ refresh: true }), fetchFloatingIps()]); }
    finally { refreshing = false; }
  }

  async function createNetwork(body: Record<string, unknown>): Promise<boolean> {
    creating = true; createError = '';
    try {
      await apiMut('네트워크 생성', () => api.post('/api/networks', body, tok(), pid()));
      await fetchNetworks();
      return true;
    } catch (e) {
      createError = e instanceof ApiError ? e.message : '생성 실패';
      return false;
    } finally { creating = false; }
  }

  async function deleteNetwork(id: string, name: string, isExternal: boolean, isShared: boolean) {
    if (isExternal || isShared) { toast.warning('외부/공유 네트워크는 삭제할 수 없습니다.'); return; }
    if (!await confirmDialog(`네트워크 "${name || id.slice(0, 8)}"를 삭제하시겠습니까?`)) return;
    deleting = id;
    try {
      await apiMut('네트워크 삭제', () => api.delete(`/api/networks/${id}`, tok(), pid()));
      await fetchNetworks();
    } catch { /* error toast shown by apiMut */ }
    finally { deleting = null; }
  }

  function openNetworkPanel(id: string) {
    selectedNetworkId = id;
    history.pushState({ networkId: id }, '', `/dashboard/network/networks/${id}`);
  }
  function closeNetworkPanel() {
    selectedNetworkId = null;
    history.pushState({}, '', '/dashboard/network/networks');
  }

  const ar = createAutoRefresh(() => { fetchNetworks(); fetchFloatingIps(); }, {
    storageKey: 'dashboard-network-networks',
    defaultActive: true, defaultInterval: 30, intervalOptions: [10, 15, 30, 60],
  });

  $effect(() => {
    const projectId = $auth.projectId;
    if (!projectId) return;
    loading = true;
    untrack(() => { fetchNetworks(); fetchFloatingIps(); fetchDefaultNetwork(); });
  });
</script>

<NetworkCreateModal bind:open={showModal} {creating} error={createError} onCreate={createNetwork} />

<div class="p-4 md:p-8">
  <PageHeader breadcrumb="NETWORK / NETWORKS" title="네트워크">
    {#snippet actions()}
      <AutoRefreshControl
        bind:active={ar.active}
        bind:intervalSeconds={ar.intervalSeconds}
        intervalOptions={ar.intervalOptions}
        {refreshing}
        onManualRefresh={forceRefresh}
      />
      <button onclick={() => showModal = true} class="bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">+ 네트워크 생성</button>
    {/snippet}
  </PageHeader>

  {#if error}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>{/if}

  {#if loading}
    <LoadingSkeleton variant="table" rows={5} />
  {:else if networks.length === 0}
    <div class="text-center py-20 text-gray-600">
      <div class="text-5xl mb-4">🌐</div>
      <p class="text-lg">네트워크가 없습니다</p>
    </div>
  {:else}
    <div class="flex flex-col gap-4">
      <NetworksTableCard
        {networks} {defaultNetworkId} {deleting} {settingDefault}
        onOpenPanel={openNetworkPanel} onSetDefault={setAsDefault} onDelete={deleteNetwork}
      />
      <FloatingIpCard
        {floatingIps}
        hasExternalNetwork={networks.some((n) => n.is_external)}
        onAllocateClick={() => (showAllocateModal = true)}
      />
    </div>
  {/if}
</div>

<FloatingIpAllocateModal
  bind:open={showAllocateModal} {networks}
  token={tok()} projectId={pid()} onAllocated={fetchFloatingIps}
/>

{#if selectedNetworkId}
  <SlidePanel onClose={closeNetworkPanel} width="w-full md:w-[60vw] max-w-2xl">
    <NetworkDetailPanel
      networkId={selectedNetworkId} apiBase="/api/networks"
      onClose={closeNetworkPanel} token={tok()} projectId={pid()}
    />
  </SlidePanel>
{/if}
