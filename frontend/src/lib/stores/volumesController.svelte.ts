import { api, ApiError } from '$lib/api/client';
import { createSwr } from '$lib/utils/swr.svelte';
import { apiMut } from '$lib/api/mutations';
import { wizard, openWizard } from '$lib/stores/wizard';
import type { Volume, Snapshot, QuotaItem } from '$lib/types/resources';
import { confirmDialog } from '$lib/stores/confirm.svelte';

interface VolumeQuotas { storage: { volumes: QuotaItem; gigabytes: QuotaItem; }; }

export interface VolumesControllerOpts {
  token: () => string | undefined;
  projectId: () => string | undefined;
}

export function createVolumesController(opts: VolumesControllerOpts) {
  const { swrGet, swrSet } = createSwr(opts.projectId);
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
  let tab = $state<'volumes' | 'snapshots'>('volumes');
  let selectedVolumeId = $state<string | null>(null);
  let autoBackupConfigs = $state<Set<string>>(new Set());
  let autoBackupToggling = $state<string | null>(null);
  let openActionMenu = $state<string | null>(null);
  let openSnapshotActionMenu = $state<string | null>(null);
  let extendTargetVol = $state<Volume | null>(null);
  let backupTargetVol = $state<Volume | null>(null);
  let snapshotTargetVol = $state<Volume | null>(null);
  let quotas = $state<VolumeQuotas | null>(null);

  async function fetchVolumes(manual = false) {
    const path = '/api/volumes';
    const cached = swrGet<Volume[]>(path);
    if (cached && volumes.length === 0) volumes = cached;
    if (manual) refreshing = true;
    try {
      volumes = await api.get<Volume[]>(path, opts.token(), opts.projectId(), manual ? { refresh: true } : undefined);
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
      snapshots = await api.get<Snapshot[]>('/api/volume-snapshots', opts.token(), opts.projectId());
    } catch { /* 오류 무시 */ }
  }

  async function fetchQuotas() {
    try {
      quotas = await api.get<VolumeQuotas>('/api/dashboard/quotas', opts.token(), opts.projectId());
    } catch { /* 오류 무시 */ }
  }

  async function fetchAutoBackupConfigs() {
    try {
      const configs = await api.post<{ volume_id: string }[]>(
        '/api/volumes/backups/auto-backup/configs', {},
        opts.token(), opts.projectId(),
      );
      autoBackupConfigs = new Set(configs.map(c => c.volume_id));
    } catch { /* 오류 무시 */ }
  }

  async function fetchAll() {
    await Promise.all([fetchVolumes(), fetchSnapshots(), fetchAutoBackupConfigs(), fetchQuotas()]);
  }

  function openVolumePanel(id: string) {
    selectedVolumeId = id;
    history.pushState({ volumeId: id }, '', `/dashboard/volumes/${id}`);
  }

  function closeVolumePanel() {
    selectedVolumeId = null;
    history.pushState({}, '', '/dashboard/volumes');
  }

  async function deleteVolume(id: string, name: string) {
    if (!(await confirmDialog(`볼륨 "${name || id.slice(0, 8)}"을 삭제하시겠습니까?`))) return;
    deleting = id;
    try {
      await apiMut('볼륨 삭제', () => api.delete(`/api/volumes/${id}`, opts.token(), opts.projectId()));
      await fetchVolumes();
    } catch {
      // error toast shown by apiMut
    } finally {
      deleting = null;
    }
  }

  async function deleteSnapshot(id: string, name: string) {
    if (!(await confirmDialog(`스냅샷 "${name || id.slice(0, 8)}"을 삭제하시겠습니까?`))) return;
    deleting = id;
    try {
      await apiMut('스냅샷 삭제', () =>
        api.delete(`/api/volume-snapshots/${id}`, opts.token(), opts.projectId()),
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
    if (!(await confirmDialog(`볼륨 "${name || id.slice(0, 8)}"을 강제 삭제하시겠습니까?\n이 작업은 오류 상태 볼륨을 강제로 제거합니다.`))) return;
    deleting = id;
    try {
      await apiMut('볼륨 강제 삭제', () => api.post(`/api/volumes/${id}/force-delete`, {}, opts.token(), opts.projectId()));
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

  async function toggleAutoBackup(volumeId: string) {
    autoBackupToggling = volumeId;
    const enabling = !autoBackupConfigs.has(volumeId);
    try {
      if (!enabling) {
        await apiMut('자동 백업 비활성화', () => api.delete(`/api/volumes/backups/auto-backup/${volumeId}`, opts.token(), opts.projectId()));
        autoBackupConfigs = new Set([...autoBackupConfigs].filter(id => id !== volumeId));
      } else {
        await apiMut('자동 백업 활성화', () => api.post(`/api/volumes/backups/auto-backup/${volumeId}`, {}, opts.token(), opts.projectId()));
        autoBackupConfigs = new Set([...autoBackupConfigs, volumeId]);
      }
    } catch {
      // error toast shown by apiMut
    } finally {
      autoBackupToggling = null;
    }
  }

  return {
    get volumes() { return volumes; },
    get snapshots() { return snapshots; },
    get loading() { return loading; },
    set loading(v: boolean) { loading = v; },
    get refreshing() { return refreshing; },
    get error() { return error; },
    get deleting() { return deleting; },
    get showModal() { return showModal; },
    set showModal(v: boolean) { showModal = v; },
    get showTransferModal() { return showTransferModal; },
    set showTransferModal(v: boolean) { showTransferModal = v; },
    get transferVolumeId() { return transferVolumeId; },
    get transferVolumeName() { return transferVolumeName; },
    get tab() { return tab; },
    set tab(v: 'volumes' | 'snapshots') { tab = v; },
    get selectedVolumeId() { return selectedVolumeId; },
    get autoBackupConfigs() { return autoBackupConfigs; },
    get autoBackupToggling() { return autoBackupToggling; },
    get openActionMenu() { return openActionMenu; },
    set openActionMenu(v: string | null) { openActionMenu = v; },
    get openSnapshotActionMenu() { return openSnapshotActionMenu; },
    set openSnapshotActionMenu(v: string | null) { openSnapshotActionMenu = v; },
    get extendTargetVol() { return extendTargetVol; },
    set extendTargetVol(v: Volume | null) { extendTargetVol = v; },
    get backupTargetVol() { return backupTargetVol; },
    set backupTargetVol(v: Volume | null) { backupTargetVol = v; },
    get snapshotTargetVol() { return snapshotTargetVol; },
    set snapshotTargetVol(v: Volume | null) { snapshotTargetVol = v; },
    get quotas() { return quotas; },
    fetchVolumes,
    fetchSnapshots,
    fetchQuotas,
    fetchAutoBackupConfigs,
    fetchAll,
    openVolumePanel,
    closeVolumePanel,
    deleteVolume,
    deleteSnapshot,
    openTransferModal,
    forceDeleteVolume,
    bootFromVolume,
    toggleAutoBackup,
  };
}
