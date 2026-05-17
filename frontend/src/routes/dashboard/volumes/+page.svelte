<script lang="ts">
  import { untrack } from 'svelte';
  import { auth } from '$lib/stores/auth';
  import { api, ApiError, memoryCache } from '$lib/api/client';
  import { apiMut } from '$lib/api/mutations';
  import type { Volume } from '$lib/types/resources';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
  import VolumeDetailPanel from '$lib/components/VolumeDetailPanel.svelte';
  import VolumeTransferModal from '$lib/components/volume/VolumeTransferModal.svelte';
  import VolumeExtendModal from '$lib/components/volume/VolumeExtendModal.svelte';
  import VolumeBackupModal from '$lib/components/volume/VolumeBackupModal.svelte';
  import VolumeSnapshotModal from '$lib/components/volume/VolumeSnapshotModal.svelte';
  import VolumeCreateModal from '$lib/components/volume/VolumeCreateModal.svelte';
  import VolumeSummaryCards from '$lib/components/volume/VolumeSummaryCards.svelte';
  import VolumeListTable from '$lib/components/volume/VolumeListTable.svelte';
  import SnapshotListTable from '$lib/components/volume/SnapshotListTable.svelte';
  import SlidePanel from '$lib/components/SlidePanel.svelte';
  import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
  import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
  import PageHeader from '$lib/components/ui/PageHeader.svelte';
  import { wizard, openWizard } from '$lib/stores/wizard';

  interface Snapshot {
    id: string;
    name: string;
    status: string;
    volume_id: string;
    size: number;
    description: string;
    created_at: string | null;
  }

  let volumes = $state<Volume[]>([]);
  let snapshots = $state<Snapshot[]>([]);
  let loading = $state(true);
  let refreshing = $state(false);
  let error = $state('');
  let deleting = $state<string | null>(null);
  let showModal = $state(false);
  let showTransferModal = $state(false);
  let transferVolumeId = $state('');
  let transferVolumeName = $state('');
  let tab = $state('volumes');

  let selectedVolumeId = $state<string | null>(null);
  let autoBackupConfigs = $state<Set<string>>(new Set());
  let autoBackupToggling = $state<string | null>(null);
  let openActionMenu = $state<string | null>(null);
  let openSnapshotActionMenu = $state<string | null>(null);
  let extendTargetVol = $state<Volume | null>(null);
  let backupTargetVol = $state<Volume | null>(null);
  let snapshotTargetVol = $state<Volume | null>(null);

  interface QuotaItem { limit: number; in_use: number; }
  interface VolumeQuotas { storage: { volumes: QuotaItem; gigabytes: QuotaItem; }; }

  let quotas = $state<VolumeQuotas | null>(null);

  function openVolumePanel(id: string) {
    selectedVolumeId = id;
    history.pushState({ volumeId: id }, '', `/dashboard/volumes/${id}`);
  }

  function closeVolumePanel() {
    selectedVolumeId = null;
    history.pushState({}, '', '/dashboard/volumes');
  }

  function swrGet<T>(path: string): T | null {
    const key = `${path}:${$auth.projectId}`;
    const c = memoryCache.get(key);
    return c ? (c.data as T) : null;
  }
  function swrSet(path: string, data: unknown) {
    memoryCache.set(`${path}:${$auth.projectId}`, { data, timestamp: Date.now() });
  }

  async function fetchVolumes(manual = false) {
    const path = '/api/volumes';
    const cached = swrGet<Volume[]>(path);
    if (cached && volumes.length === 0) volumes = cached;
    if (manual) refreshing = true;
    try {
      volumes = await api.get<Volume[]>(path, $auth.token ?? undefined, $auth.projectId ?? undefined, manual ? { refresh: true } : undefined);
      swrSet(path, volumes);
      error = '';
    } catch (e) {
      if (!cached) error = e instanceof ApiError ? `조회 실패 (${e.status})` : '서버 오류';
    } finally {
      loading = false;
      refreshing = false;
    }
  }

  async function fetchSnapshots() {
    try {
      snapshots = await api.get<Snapshot[]>('/api/volume-snapshots', $auth.token ?? undefined, $auth.projectId ?? undefined);
    } catch { /* 오류 무시 */ }
  }

  async function fetchQuotas() {
    try {
      quotas = await api.get<VolumeQuotas>('/api/dashboard/quotas', $auth.token ?? undefined, $auth.projectId ?? undefined);
    } catch { /* 오류 무시 */ }
  }

  async function deleteVolume(id: string, name: string) {
    if (!confirm(`볼륨 "${name || id.slice(0, 8)}"을 삭제하시겠습니까?`)) return;
    deleting = id;
    try {
      await apiMut('볼륨 삭제', () => api.delete(`/api/volumes/${id}`, $auth.token ?? undefined, $auth.projectId ?? undefined));
      await fetchVolumes();
    } catch {
      // error toast shown by apiMut
    } finally {
      deleting = null;
    }
  }

  async function deleteSnapshot(id: string, name: string) {
    if (!confirm(`스냅샷 "${name || id.slice(0, 8)}"을 삭제하시겠습니까?`)) return;
    deleting = id;
    try {
      await apiMut('스냅샷 삭제', () =>
        api.delete(`/api/volume-snapshots/${id}`, $auth.token ?? undefined, $auth.projectId ?? undefined)
      );
      await fetchSnapshots();
    } catch {
      // error toast shown by apiMut
    } finally {
      deleting = null;
    }
  }

  function openTransferModal(id: string, name: string) {
    transferVolumeId = id;
    transferVolumeName = name;
    showTransferModal = true;
  }

  async function forceDeleteVolume(id: string, name: string) {
    if (!confirm(`볼륨 "${name || id.slice(0, 8)}"을 강제 삭제하시겠습니까?\n이 작업은 오류 상태 볼륨을 강제로 제거합니다.`)) return;
    deleting = id;
    try {
      await apiMut('볼륨 강제 삭제', () => api.post(`/api/volumes/${id}/force-delete`, {}, $auth.token ?? undefined, $auth.projectId ?? undefined));
      await fetchVolumes();
    } catch {
      // error toast shown by apiMut
    } finally {
      deleting = null;
    }
  }

  function bootFromVolume(vol: Volume) {
    wizard.update(s => ({
      ...s,
      bootSource: 'volume',
      bootVolumeId: vol.id,
      bootVolumeName: vol.name,
      imageId: null,
      imageName: null,
    }));
    openWizard();
  }

  async function fetchAutoBackupConfigs() {
    try {
      const configs = await api.post<{ volume_id: string }[]>(
        '/api/volumes/backups/auto-backup/configs', {},
        $auth.token ?? undefined, $auth.projectId ?? undefined
      );
      autoBackupConfigs = new Set(configs.map(c => c.volume_id));
    } catch { /* 오류 무시 */ }
  }

  async function toggleAutoBackup(volumeId: string) {
    autoBackupToggling = volumeId;
    const enabling = !autoBackupConfigs.has(volumeId);
    try {
      if (!enabling) {
        await apiMut('자동 백업 비활성화', () => api.delete(`/api/volumes/backups/auto-backup/${volumeId}`, $auth.token ?? undefined, $auth.projectId ?? undefined));
        autoBackupConfigs = new Set([...autoBackupConfigs].filter(id => id !== volumeId));
      } else {
        await apiMut('자동 백업 활성화', () => api.post(`/api/volumes/backups/auto-backup/${volumeId}`, {}, $auth.token ?? undefined, $auth.projectId ?? undefined));
        autoBackupConfigs = new Set([...autoBackupConfigs, volumeId]);
      }
    } catch {
      // error toast shown by apiMut
    } finally {
      autoBackupToggling = null;
    }
  }

  const ar = createAutoRefresh(() => { fetchVolumes(); fetchSnapshots(); }, {
    storageKey: 'dashboard-volumes',
    defaultActive: true,
    defaultInterval: 10,
    intervalOptions: [10, 15, 30, 60],
  });

  $effect(() => {
    const projectId = $auth.projectId;
    if (!projectId) return;
    loading = true;
    untrack(() => { fetchVolumes(); fetchAutoBackupConfigs(); fetchSnapshots(); fetchQuotas(); });
  });
</script>

<svelte:window
  onkeydown={(e) => { if (e.key === 'Escape' && selectedVolumeId) closeVolumePanel(); }}
/>

<VolumeCreateModal bind:open={showModal} onCreated={() => fetchVolumes()} />

<div class="p-4 md:p-8">
  <PageHeader breadcrumb="VOLUMES / BLOCK VOLUMES" title="블록 볼륨">
    {#snippet actions()}
      <AutoRefreshControl
        bind:active={ar.active}
        bind:intervalSeconds={ar.intervalSeconds}
        intervalOptions={ar.intervalOptions}
        refreshing={refreshing}
        onManualRefresh={() => fetchVolumes(true)}
      />
      <button onclick={() => showModal = true} class="bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">+ 볼륨 생성</button>
    {/snippet}
  </PageHeader>

  {#if error}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>{/if}

  {#if loading}
    <div class="grid grid-cols-3 gap-3.5 mb-5">
      {#each [1,2,3] as _}
        <div class="bg-gray-900 border border-gray-800 rounded-2xl p-5 animate-pulse">
          <div class="h-3 w-20 bg-gray-800 rounded mb-3"></div>
          <div class="h-8 w-16 bg-gray-800 rounded mb-3"></div>
          <div class="h-1.5 w-full bg-gray-800 rounded-full"></div>
        </div>
      {/each}
    </div>
    <LoadingSkeleton variant="table" rows={5} />
  {:else if volumes.length === 0}
    <div class="text-center py-20 text-gray-600">
      <div class="text-5xl mb-4">💾</div>
      <p class="text-lg">볼륨이 없습니다</p>
      <button onclick={() => showModal = true} class="text-blue-400 hover:text-blue-300 text-sm mt-2 inline-block">첫 볼륨을 생성하세요 →</button>
    </div>
  {:else}
    <VolumeSummaryCards {volumes} {snapshots} {quotas} />

    <div class="flex gap-1 mb-4 border-b border-gray-800">
      <button onclick={() => tab = 'volumes'}
        class="px-4 py-2 text-[13px] font-medium border-b-2 -mb-px transition-colors {tab === 'volumes' ? 'border-blue-500 text-white' : 'border-transparent text-gray-400 hover:text-gray-200'}">
        볼륨 {volumes.length}
      </button>
      <button onclick={() => tab = 'snapshots'}
        class="px-4 py-2 text-[13px] font-medium border-b-2 -mb-px transition-colors {tab === 'snapshots' ? 'border-blue-500 text-white' : 'border-transparent text-gray-400 hover:text-gray-200'}">
        스냅샷 {snapshots.length}
      </button>
    </div>

    {#if tab === 'volumes'}
      <VolumeListTable
        {volumes}
        {selectedVolumeId}
        {deleting}
        {autoBackupConfigs}
        {autoBackupToggling}
        {openActionMenu}
        isSystemAdmin={!!$auth.isSystemAdmin}
        onOpenDetail={openVolumePanel}
        onActionMenuOpen={(id) => (openActionMenu = id)}
        onActionMenuClose={() => (openActionMenu = null)}
        onBoot={bootFromVolume}
        onExtend={(vol) => (extendTargetVol = vol)}
        onBackup={(vol) => (backupTargetVol = vol)}
        onSnapshot={(vol) => (snapshotTargetVol = vol)}
        onTransfer={openTransferModal}
        onForceDelete={forceDeleteVolume}
        onDelete={deleteVolume}
        onToggleAutoBackup={toggleAutoBackup}
      />
    {:else}
      <SnapshotListTable
        {snapshots}
        {deleting}
        {openSnapshotActionMenu}
        onActionMenuOpen={(id) => (openSnapshotActionMenu = id)}
        onActionMenuClose={() => (openSnapshotActionMenu = null)}
        onDelete={deleteSnapshot}
      />
    {/if}
  {/if}
</div>

<!-- Volume Detail Panel -->
{#if selectedVolumeId}
  <SlidePanel onClose={closeVolumePanel} width="w-full md:w-[60vw] max-w-2xl">
    <VolumeDetailPanel
      volumeId={selectedVolumeId}
      onClose={closeVolumePanel}
      onDeleted={() => { fetchVolumes(); closeVolumePanel(); }}
    />
  </SlidePanel>
{/if}

<!-- Volume Transfer Modal -->
{#if showTransferModal}
  <VolumeTransferModal
    volumeId={transferVolumeId}
    volumeName={transferVolumeName}
    onClose={() => showTransferModal = false}
    onTransferred={() => { fetchVolumes(); showTransferModal = false; }}
  />
{/if}

<!-- Volume Extend Modal -->
<VolumeExtendModal
  volume={extendTargetVol}
  onclose={() => extendTargetVol = null}
  onsuccess={() => { extendTargetVol = null; fetchVolumes(true); }}
/>

<!-- Volume Backup Modal -->
<VolumeBackupModal
  volume={backupTargetVol}
  onclose={() => backupTargetVol = null}
  onsuccess={() => { backupTargetVol = null; }}
/>

<!-- Volume Snapshot Modal -->
<VolumeSnapshotModal
  volume={snapshotTargetVol}
  onclose={() => snapshotTargetVol = null}
  onsuccess={() => { snapshotTargetVol = null; fetchSnapshots(); }}
/>
