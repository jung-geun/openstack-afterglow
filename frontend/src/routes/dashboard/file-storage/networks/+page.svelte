<script lang="ts">
	import { confirmDialog } from '$lib/stores/confirm.svelte';
  import { untrack } from 'svelte';
  import { auth } from '$lib/stores/auth';
  import { api, ApiError } from '$lib/api/client';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
  import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
  import PageHeader from '$lib/components/ui/PageHeader.svelte';
  import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
  import type { ShareNetwork } from '$lib/types/shareNetwork';
  import ShareNetworkCreateModal from '$lib/components/dashboard/file-storage/networks/ShareNetworkCreateModal.svelte';
  import ShareNetworkTable from '$lib/components/dashboard/file-storage/networks/ShareNetworkTable.svelte';
  import { toast } from '$lib/stores/toast';
  import { betaFeatures } from '$lib/stores/betaFeatures';
  import BetaFeatureGate from '$lib/components/ui/BetaFeatureGate.svelte';

  let networks = $state<ShareNetwork[]>([]);
  let loading = $state(true);
  let refreshing = $state(false);
  let deleting = $state<string | null>(null);
  let error = $state('');
  let showModal = $state(false);
  let creating = $state(false);

  const token = $derived($auth.token ?? undefined);
  const projectId = $derived($auth.projectId ?? undefined);
  const shareNetworksEnabled = $derived($betaFeatures.fileStorageShareNetworks);

  function clearNetworksState() {
    networks = [];
    error = '';
  }


  async function fetchNetworks(opts?: { refresh?: boolean }) {
    if (!shareNetworksEnabled) {
      clearNetworksState();
      loading = false;
      return;
    }
    try {
      networks = await api.get<ShareNetwork[]>('/api/v1/share-networks', token, projectId, opts);
      error = '';
    } catch (e) {
      error = e instanceof ApiError ? `조회 실패 (${e.status})` : '서버 오류';
    } finally {
      loading = false;
    }
  }

  async function createNetwork(form: { name: string; description: string; neutron_net_id: string; neutron_subnet_id: string }): Promise<boolean> {
    if (!shareNetworksEnabled) return false;
    creating = true;
    try {
      await api.post('/api/v1/share-networks', form, token, projectId);
      await fetchNetworks();
      return true;
    } finally {
      creating = false;
    }
  }

  async function deleteNetwork(id: string, name: string) {
    if (!shareNetworksEnabled) return;
    if (!await confirmDialog(`Share 네트워크 "${name || id.slice(0, 8)}"을 삭제하시겠습니까?\n이 네트워크를 사용 중인 파일 스토리지가 있으면 삭제할 수 없습니다.`)) return;
    deleting = id;
    try {
      await api.delete(`/api/v1/share-networks/${id}`, token, projectId);
      await fetchNetworks();
    } catch (e) {
      toast.error('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
    } finally {
      deleting = null;
    }
  }

  const ar = createAutoRefresh(() => fetchNetworks(), {
    storageKey: 'dashboard-file-storage-networks',
    defaultActive: true,
    defaultInterval: 30,
    intervalOptions: [10, 15, 30, 60],
  });

  $effect(() => {
    if (!shareNetworksEnabled) {
      clearNetworksState();
      loading = false;
      return;
    }
    if (!$auth.projectId) return;
    loading = true;
    untrack(() => fetchNetworks());
  });
</script>

{#if !shareNetworksEnabled}
  <div class="p-4 md:p-8">
    <BetaFeatureGate title="Share 네트워크는 베타 기능입니다" />
  </div>
{:else}
<ShareNetworkCreateModal bind:open={showModal} {creating} {token} {projectId} onCreate={createNetwork} />

<div class="p-4 md:p-8">
  <PageHeader breadcrumb="FILE STORAGE / NETWORKS" title="Share 네트워크">
    {#snippet actions()}
      <AutoRefreshControl
        bind:active={ar.active}
        bind:intervalSeconds={ar.intervalSeconds}
        intervalOptions={ar.intervalOptions}
        refreshing={refreshing || loading}
        onManualRefresh={async () => { refreshing = true; try { await fetchNetworks({ refresh: true }); } finally { refreshing = false; } }}
      />
      <button onclick={() => { showModal = true; }}
        class="bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
        + Share 네트워크 생성
      </button>
    {/snippet}
  </PageHeader>

  <div class="mb-6 space-y-2">
    <p class="text-sm text-gray-500">파일 스토리지(Manila)를 Neutron 네트워크에 연결하는 Share Network를 관리합니다.</p>
    <div class="flex items-start gap-2 px-4 py-3 rounded-lg bg-blue-950/30 border border-blue-900/40 text-blue-300 text-xs">
      <svg class="w-4 h-4 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
      </svg>
      <span>
        현재 환경(DHSS=False 드라이버)에서는 Share Network 없이 파일 스토리지가 생성되며, VM 연결은 IP 접근 규칙으로 제어됩니다.
        Share Network는 DHSS=True 드라이버를 사용하는 경우에만 필요하며, 이 환경에서는 생성해도 실제로 사용되지 않습니다.
      </span>
    </div>
  </div>

  {#if error}
    <div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>
  {/if}

  {#if loading}
    <LoadingSkeleton variant="table" rows={4} />
  {:else if networks.length === 0}
    <div class="text-center py-20 text-gray-600">
      <div class="text-5xl mb-4">🔗</div>
      <p class="text-lg">Share 네트워크가 없습니다</p>
      <button onclick={() => { showModal = true; }} class="text-blue-400 hover:text-blue-300 text-sm mt-2 inline-block">첫 Share 네트워크를 생성하세요 →</button>
    </div>
  {:else}
    <ShareNetworkTable {networks} {deleting} onDelete={deleteNetwork} />
  {/if}
</div>
{/if}
