<script lang="ts">
  import { auth } from '$lib/stores/auth';
  import { untrack } from 'svelte';
  import { goto } from '$app/navigation';
  import { createK3sClusterDetailStore, provideK3sClusterDetail } from '$lib/stores/k3sClusterDetail.svelte';
  import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
  import K3sClusterHeader from '$lib/components/k3s/K3sClusterHeader.svelte';
  import K3sDeleteProgress from '$lib/components/k3s/K3sDeleteProgress.svelte';
  import K3sClusterInfoCard from '$lib/components/k3s/K3sClusterInfoCard.svelte';
  import K3sClusterNodesCard from '$lib/components/k3s/K3sClusterNodesCard.svelte';
  import K3sClusterVmList from '$lib/components/k3s/K3sClusterVmList.svelte';
  import K3sNodegroupsSection from '$lib/components/k3s/K3sNodegroupsSection.svelte';
  import K3sInstanceViewerOverlay from '$lib/components/k3s/K3sInstanceViewerOverlay.svelte';
  import K3sClusterNetworksCard from '$lib/components/k3s/K3sClusterNetworksCard.svelte';
  import K3sNamespaceSelector from '$lib/components/k3s/K3sNamespaceSelector.svelte';
  import K3sClusterConfigMapsCard from '$lib/components/k3s/K3sClusterConfigMapsCard.svelte';
  import K3sClusterSecretsCard from '$lib/components/k3s/K3sClusterSecretsCard.svelte';
  import K3sCloudShellOverlay from '$lib/components/k3s/K3sCloudShellOverlay.svelte';

  interface Props {
    clusterId: string;
    onClose?: () => void;
    adminMode?: boolean;
  }

  let { clusterId, onClose, adminMode = false }: Props = $props();

  const s = createK3sClusterDetailStore({
    clusterId: () => clusterId,
    token: () => $auth.token ?? undefined,
    projectId: () => $auth.projectId ?? undefined,
    adminMode: () => adminMode,
    onClose: onClose ?? (() => goto('/dashboard/drover')),
  });
  provideK3sClusterDetail(s);

  createAutoRefresh(() => untrack(() => {
    s.loadCluster();
    s.loadHealth();
  }), {
    storageKey: 'k3s-cluster-events',
    defaultActive: true,
    defaultInterval: 15,
    intervalOptions: [10, 15, 30, 60]
  });

  $effect(() => {
    if (!$auth.projectId || !clusterId) return;
    s.reset();
    untrack(() => s.loadCluster());
  });

  $effect(() => {
    if (s.cluster?.status === 'ACTIVE' && !s.initialCheckDone) {
      s.initialCheckDone = true;
      untrack(() => {
        s.checkKubeconfig();
        s.loadHealth();
      });
    }
  });
</script>

<div class="relative h-full">
  {#if s.shellOpen}
    <K3sCloudShellOverlay />
  {/if}

  {#if s.viewingInstanceId}
    <K3sInstanceViewerOverlay />
  {/if}

  <div class="p-6">
    <div class="mb-5 flex items-center justify-between">
      {#if onClose}
        <button onclick={onClose} class="text-gray-400 hover:text-gray-200 text-sm transition-colors">
          ✕ 닫기
        </button>
      {:else}
        <a href="/dashboard/drover" class="text-gray-400 hover:text-gray-200 text-sm transition-colors">
          ← Drover
        </a>
      {/if}
    </div>

    {#if s.loading}
      <div class="animate-pulse space-y-4">
        <div class="h-8 bg-gray-800 rounded w-64"></div>
        <div class="h-40 bg-gray-800 rounded"></div>
      </div>
    {:else if s.error}
      <div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">{s.error}</div>
    {:else if s.cluster}
      <K3sClusterHeader />
      {#if s.deleteProgress}<K3sDeleteProgress />{/if}
      <div class="grid grid-cols-1 @3xl/panel:grid-cols-2 gap-3 mb-4">
        <K3sClusterInfoCard />
        <K3sClusterNodesCard />
      </div>
      <K3sClusterVmList />
      <K3sNodegroupsSection />
      <K3sClusterNetworksCard />
      <K3sNamespaceSelector />
      <K3sClusterConfigMapsCard />
      <K3sClusterSecretsCard />
    {/if}
  </div>
</div>
