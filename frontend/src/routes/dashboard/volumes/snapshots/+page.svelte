<script lang="ts">
	import { confirmDialog } from '$lib/stores/confirm.svelte';
  import { untrack } from 'svelte';
  import { auth } from '$lib/stores/auth';
  import { api, ApiError } from '$lib/api/client';
  import type { Volume, VolumeSnapshot } from '$lib/types/volume';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
  import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
  import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
  import PageHeader from '$lib/components/ui/PageHeader.svelte';
  import VolumeSnapshotCreateModal from '$lib/components/volume/snapshots/VolumeSnapshotCreateModal.svelte';
  import VolumeSnapshotsTable from '$lib/components/volume/snapshots/VolumeSnapshotsTable.svelte';
  import VolumeSnapshotsEmptyState from '$lib/components/volume/snapshots/VolumeSnapshotsEmptyState.svelte';
  import { toast } from '$lib/stores/toast';
  import { betaFeatures } from '$lib/stores/betaFeatures';
  import BetaFeatureGate from '$lib/components/ui/BetaFeatureGate.svelte';

  let snapshots = $state<VolumeSnapshot[]>([]);
  let volumes = $state<Volume[]>([]);
  let loading = $state(true);
  let refreshing = $state(false);
  let error = $state('');
  let deleting = $state<string | null>(null);
  let showModal = $state(false);
  const volumeSnapshotsEnabled = $derived($betaFeatures.volumeSnapshots);

  function clearSnapshotsState() {
    snapshots = [];
    volumes = [];
    error = '';
  }


  async function fetchSnapshots() {
    if (!volumeSnapshotsEnabled) {
      clearSnapshotsState();
      loading = false;
      return;
    }
    try {
      snapshots = await api.get<VolumeSnapshot[]>('/api/v1/volume-snapshots', $auth.token ?? undefined, $auth.projectId ?? undefined);
      error = '';
    } catch (e) {
      error = e instanceof ApiError ? `조회 실패 (${e.status})` : '서버 오류';
    } finally {
      loading = false;
    }
  }

  async function fetchVolumes() {
    if (!volumeSnapshotsEnabled) {
      volumes = [];
      return;
    }
    try {
      volumes = await api.get<Volume[]>('/api/v1/volumes', $auth.token ?? undefined, $auth.projectId ?? undefined);
    } catch { /* ignore */ }
  }

  async function createSnapshot(form: { volume_id: string; name: string; description: string; force: boolean }): Promise<string | true> {
    if (!volumeSnapshotsEnabled) return '볼륨 스냅샷 베타 기능이 꺼져 있습니다.';
    try {
      await api.post('/api/v1/volume-snapshots', form, $auth.token ?? undefined, $auth.projectId ?? undefined);
      await fetchSnapshots();
      return true;
    } catch (e) {
      return e instanceof ApiError ? e.message : '생성 실패';
    }
  }

  async function deleteSnapshot(id: string, name: string) {
    if (!volumeSnapshotsEnabled) return;
    if (!await confirmDialog(`스냅샷 "${name || id.slice(0, 8)}"을 삭제하시겠습니까?`)) return;
    deleting = id;
    try {
      await api.delete(`/api/v1/volume-snapshots/${id}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
      await fetchSnapshots();
    } catch (e) {
      toast.error('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
    } finally {
      deleting = null;
    }
  }

  async function forceRefresh() {
    refreshing = true;
    try { await fetchSnapshots(); } finally { refreshing = false; }
  }

  const ar = createAutoRefresh(() => fetchSnapshots(), {
    storageKey: 'dashboard-volume-snapshots',
    defaultActive: true,
    defaultInterval: 15,
    intervalOptions: [10, 15, 30, 60],
  });

  $effect(() => {
    const pid = $auth.projectId;
    if (!volumeSnapshotsEnabled) {
      clearSnapshotsState();
      loading = false;
      return;
    }
    if (!pid) return;
    untrack(() => { fetchSnapshots(); fetchVolumes(); });
  });
</script>

{#if !volumeSnapshotsEnabled}
  <div class="p-4 md:p-8">
    <BetaFeatureGate title="볼륨 스냅샷은 베타 기능입니다" />
  </div>
{:else}
<VolumeSnapshotCreateModal bind:open={showModal} {volumes} onCreate={createSnapshot} />

<div class="p-4 md:p-8">
  <PageHeader breadcrumb="VOLUMES / SNAPSHOTS" title="볼륨 스냅샷">
    {#snippet actions()}
      <AutoRefreshControl
        bind:active={ar.active}
        bind:intervalSeconds={ar.intervalSeconds}
        intervalOptions={ar.intervalOptions}
        refreshing={refreshing}
        onManualRefresh={forceRefresh}
      />
      <button onclick={() => showModal = true} class="bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">+ 스냅샷 생성</button>
    {/snippet}
  </PageHeader>

  {#if error}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>{/if}

  {#if loading}
    <LoadingSkeleton variant="table" rows={4} />
  {:else if snapshots.length === 0}
    <VolumeSnapshotsEmptyState onCreate={() => showModal = true} />
  {:else}
    <VolumeSnapshotsTable {snapshots} {deleting} onDelete={deleteSnapshot} />
  {/if}
</div>
{/if}
