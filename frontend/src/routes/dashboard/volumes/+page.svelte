<script lang="ts">
  import { untrack } from 'svelte';
  import { auth } from '$lib/stores/auth';
  import { createVolumesController } from '$lib/stores/volumesController.svelte';
  import VolumeDetailPanel from '$lib/components/VolumeDetailPanel.svelte';
  import VolumeCreateModal from '$lib/components/volume/VolumeCreateModal.svelte';
  import VolumeSummaryCards from '$lib/components/volume/VolumeSummaryCards.svelte';
  import VolumeListTable from '$lib/components/volume/VolumeListTable.svelte';
  import SnapshotListTable from '$lib/components/volume/SnapshotListTable.svelte';
  import SlidePanel from '$lib/components/SlidePanel.svelte';
  import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
  import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
  import PageHeader from '$lib/components/ui/PageHeader.svelte';
  import VolumesTabs from '$lib/components/volume/VolumesTabs.svelte';
  import VolumesLoadingState from '$lib/components/volume/VolumesLoadingState.svelte';
  import VolumesEmptyState from '$lib/components/volume/VolumesEmptyState.svelte';
  import VolumesModalStack from '$lib/components/volume/VolumesModalStack.svelte';

  const ctrl = createVolumesController({
    token: () => $auth.token ?? undefined,
    projectId: () => $auth.projectId ?? undefined,
  });

  const ar = createAutoRefresh(() => { ctrl.fetchVolumes(); ctrl.fetchSnapshots(); }, {
    storageKey: 'dashboard-volumes',
    defaultActive: true,
    defaultInterval: 10,
    intervalOptions: [10, 15, 30, 60],
  });

  $effect(() => {
    const projectId = $auth.projectId;
    if (!projectId) return;
    ctrl.loading = true;
    untrack(() => ctrl.fetchAll());
  });
</script>

<svelte:window
  onkeydown={(e) => { if (e.key === 'Escape' && ctrl.selectedVolumeId) ctrl.closeVolumePanel(); }}
/>

<VolumeCreateModal bind:open={ctrl.showModal} onCreated={() => ctrl.fetchVolumes()} />

<div class="p-4 md:p-8">
  <PageHeader breadcrumb="VOLUMES / BLOCK VOLUMES" title="블록 볼륨">
    {#snippet actions()}
      <AutoRefreshControl
        bind:active={ar.active}
        bind:intervalSeconds={ar.intervalSeconds}
        intervalOptions={ar.intervalOptions}
        refreshing={ctrl.refreshing}
        onManualRefresh={() => ctrl.fetchVolumes(true)}
      />
      <button onclick={() => ctrl.showModal = true} class="bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">+ 볼륨 생성</button>
    {/snippet}
  </PageHeader>

  {#if ctrl.error}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{ctrl.error}</div>{/if}

  {#if ctrl.loading}
    <VolumesLoadingState />
  {:else if ctrl.volumes.length === 0}
    <VolumesEmptyState onCreate={() => ctrl.showModal = true} />
  {:else}
    <VolumeSummaryCards volumes={ctrl.volumes} snapshots={ctrl.snapshots} quotas={ctrl.quotas} />
    <VolumesTabs bind:tab={ctrl.tab} volumeCount={ctrl.volumes.length} snapshotCount={ctrl.snapshots.length} />

    {#if ctrl.tab === 'volumes'}
      <VolumeListTable
        volumes={ctrl.volumes}
        selectedVolumeId={ctrl.selectedVolumeId}
        deleting={ctrl.deleting}
        autoBackupConfigs={ctrl.autoBackupConfigs}
        autoBackupToggling={ctrl.autoBackupToggling}
        openActionMenu={ctrl.openActionMenu}
        isSystemAdmin={!!$auth.isSystemAdmin}
        onOpenDetail={ctrl.openVolumePanel}
        onActionMenuOpen={(id) => (ctrl.openActionMenu = id)}
        onActionMenuClose={() => (ctrl.openActionMenu = null)}
        onBoot={ctrl.bootFromVolume}
        onExtend={(vol) => (ctrl.extendTargetVol = vol)}
        onBackup={(vol) => (ctrl.backupTargetVol = vol)}
        onSnapshot={(vol) => (ctrl.snapshotTargetVol = vol)}
        onTransfer={ctrl.openTransferModal}
        onForceDelete={ctrl.forceDeleteVolume}
        onDelete={ctrl.deleteVolume}
        onToggleAutoBackup={ctrl.toggleAutoBackup}
      />
    {:else}
      <SnapshotListTable
        snapshots={ctrl.snapshots}
        deleting={ctrl.deleting}
        openSnapshotActionMenu={ctrl.openSnapshotActionMenu}
        onActionMenuOpen={(id) => (ctrl.openSnapshotActionMenu = id)}
        onActionMenuClose={() => (ctrl.openSnapshotActionMenu = null)}
        onDelete={ctrl.deleteSnapshot}
      />
    {/if}
  {/if}
</div>

{#if ctrl.selectedVolumeId}
  <SlidePanel onClose={ctrl.closeVolumePanel} width="w-full md:w-[60vw] max-w-2xl">
    <VolumeDetailPanel
      volumeId={ctrl.selectedVolumeId}
      onClose={ctrl.closeVolumePanel}
      onDeleted={() => { ctrl.fetchVolumes(); ctrl.closeVolumePanel(); }}
    />
  </SlidePanel>
{/if}

<VolumesModalStack
  transferVolumeId={ctrl.transferVolumeId}
  transferVolumeName={ctrl.transferVolumeName}
  showTransfer={ctrl.showTransferModal}
  extendTarget={ctrl.extendTargetVol}
  backupTarget={ctrl.backupTargetVol}
  snapshotTarget={ctrl.snapshotTargetVol}
  onCloseTransfer={() => ctrl.showTransferModal = false}
  onTransferred={() => { ctrl.fetchVolumes(); ctrl.showTransferModal = false; }}
  onCloseExtend={() => ctrl.extendTargetVol = null}
  onExtendSuccess={() => { ctrl.extendTargetVol = null; ctrl.fetchVolumes(true); }}
  onCloseBackup={() => ctrl.backupTargetVol = null}
  onCloseSnapshot={() => ctrl.snapshotTargetVol = null}
  onSnapshotSuccess={() => { ctrl.snapshotTargetVol = null; ctrl.fetchSnapshots(); }}
/>
