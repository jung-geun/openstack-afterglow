import { api, ApiError } from '$lib/api/client';
import { KNOWN_DISTROS } from '$lib/utils/imageOs';
import type { ImageInfo } from '$lib/types/compute';
import { confirmDialog } from '$lib/stores/confirm.svelte';
import { toast } from '$lib/stores/toast';

export interface ImagesControllerOpts {
  token: () => string | undefined;
  projectId: () => string | undefined;
}

export function createImagesController(opts: ImagesControllerOpts) {
  let images = $state<ImageInfo[]>([]);
  let loading = $state(true);
  let refreshing = $state(false);
  let error = $state('');
  let deleting = $state<string | null>(null);
  let togglingId = $state<string | null>(null);
  let selectedImageId = $state<string | null>(null);
  let distroFilter = $state('all');
  let sortOrder = $state<'asc' | 'desc'>('desc');
  let editTarget = $state<ImageInfo | null>(null);
  let showUploadModal = $state(false);
  let uploadInitialFile = $state<File | null>(null);

  const filteredImages = $derived.by(() => {
    let list = [...images];
    if (distroFilter !== 'all') {
      if (distroFilter === 'other') {
        list = list.filter(img => !img.os_distro || !KNOWN_DISTROS.includes(img.os_distro));
      } else {
        list = list.filter(img => img.os_distro === distroFilter);
      }
    }
    list.sort((a, b) => {
      const da = a.created_at ?? '';
      const db = b.created_at ?? '';
      return sortOrder === 'desc' ? db.localeCompare(da) : da.localeCompare(db);
    });
    return list;
  });

  const distroGroups = $derived.by(() => {
    const counts: Record<string, number> = { all: images.length };
    for (const img of images) {
      const d = img.os_distro ?? 'other';
      const key = KNOWN_DISTROS.includes(d) ? d : 'other';
      counts[key] = (counts[key] ?? 0) + 1;
    }
    return counts;
  });

  function openImagePanel(id: string) {
    selectedImageId = id;
    history.pushState({ imageId: id }, '', `/dashboard/compute/images/${id}`);
  }

  function closeImagePanel() {
    selectedImageId = null;
    history.pushState({}, '', '/dashboard/compute/images');
  }

  function handleImageDeleted(id: string) {
    images = images.filter(img => img.id !== id);
  }

  function updateImage(updated: ImageInfo) {
    images = images.map(i => i.id === updated.id ? updated : i);
  }

  async function fetchImages(fetchOpts?: { refresh?: boolean }) {
    try {
      images = await api.get<ImageInfo[]>('/api/v1/images', opts.token(), opts.projectId(), fetchOpts);
      error = '';
    } catch (e) {
      error = e instanceof ApiError ? `조회 실패 (${e.status})` : '서버 오류';
    } finally {
      loading = false;
    }
  }

  async function deleteImage(id: string, name: string) {
    if (!(await confirmDialog(`이미지 "${name}"을 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.`))) return;
    deleting = id;
    try {
      await api.delete(`/api/v1/images/${id}`, opts.token(), opts.projectId());
      images = images.filter(img => img.id !== id);
    } catch (e) {
      toast.error('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
    } finally {
      deleting = null;
    }
  }

  async function toggleActivation(img: ImageInfo) {
    togglingId = img.id;
    try {
      const action = img.status === 'active' ? 'deactivate' : 'reactivate';
      await api.post(`/api/v1/images/${img.id}/${action}`, {}, opts.token(), opts.projectId());
      await fetchImages({ refresh: true });
    } catch (e) {
      toast.error('상태 변경 실패: ' + (e instanceof ApiError ? e.message : String(e)));
    } finally {
      togglingId = null;
    }
  }

  async function forceRefresh() {
    refreshing = true;
    try {
      await fetchImages({ refresh: true });
    } finally {
      refreshing = false;
    }
  }

  return {
    get images() { return images; },
    get loading() { return loading; },
    set loading(v: boolean) { loading = v; },
    get refreshing() { return refreshing; },
    get error() { return error; },
    get deleting() { return deleting; },
    get togglingId() { return togglingId; },
    get selectedImageId() { return selectedImageId; },
    get distroFilter() { return distroFilter; },
    set distroFilter(v: string) { distroFilter = v; },
    get sortOrder() { return sortOrder; },
    set sortOrder(v: 'asc' | 'desc') { sortOrder = v; },
    get editTarget() { return editTarget; },
    set editTarget(v: ImageInfo | null) { editTarget = v; },
    get showUploadModal() { return showUploadModal; },
    set showUploadModal(v: boolean) { showUploadModal = v; },
    get uploadInitialFile() { return uploadInitialFile; },
    set uploadInitialFile(v: File | null) { uploadInitialFile = v; },
    get filteredImages() { return filteredImages; },
    get distroGroups() { return distroGroups; },
    openImagePanel,
    closeImagePanel,
    handleImageDeleted,
    updateImage,
    fetchImages,
    deleteImage,
    toggleActivation,
    forceRefresh,
  };
}
