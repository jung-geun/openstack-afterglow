<script lang="ts">
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

  let networks = $state<ShareNetwork[]>([]);
  let loading = $state(true);
  let refreshing = $state(false);
  let deleting = $state<string | null>(null);
  let error = $state('');
  let showModal = $state(false);
  let creating = $state(false);

  const token = $derived($auth.token ?? undefined);
  const projectId = $derived($auth.projectId ?? undefined);

  async function fetchNetworks(opts?: { refresh?: boolean }) {
    try {
      networks = await api.get<ShareNetwork[]>('/api/share-networks', token, projectId, opts);
      error = '';
    } catch (e) {
      error = e instanceof ApiError ? `조회 실패 (${e.status})` : '서버 오류';
    } finally {
      loading = false;
    }
  }

  async function createNetwork(form: { name: string; description: string; neutron_net_id: string; neutron_subnet_id: string }): Promise<boolean> {
    creating = true;
    try {
      await api.post('/api/share-networks', form, token, projectId);
      await fetchNetworks();
      return true;
    } finally {
      creating = false;
    }
  }

  async function deleteNetwork(id: string, name: string) {
    if (!confirm(`Share 네트워크 "${name || id.slice(0, 8)}"을 삭제하시겠습니까?\n이 네트워크를 사용 중인 파일 스토리지가 있으면 삭제할 수 없습니다.`)) return;
    deleting = id;
    try {
      await api.delete(`/api/share-networks/${id}`, token, projectId);
      await fetchNetworks();
    } catch (e) {
      alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
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
    if (!$auth.projectId) return;
    loading = true;
    untrack(() => fetchNetworks());
  });
</script>

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

  <p class="text-sm text-gray-500 mb-6">파일 스토리지(Manila)를 Neutron 네트워크에 연결하는 Share Network를 관리합니다. NFS 프로토콜 사용 시 필수입니다.</p>

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
