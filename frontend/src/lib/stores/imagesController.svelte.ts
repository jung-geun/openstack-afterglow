import { api, ApiError } from '$lib/api/client';
import { KNOWN_DISTROS } from '$lib/utils/imageOs';
import { imageReferenceMatchesQuery, imageReferenceMatchScore, parseImageReference } from '$lib/utils/imageReference';
import type { ImageInfo } from '$lib/types/compute';
import { confirmDialog } from '$lib/stores/confirm.svelte';
import { toast } from '$lib/stores/toast';
import { executeBulkMutations, type BulkMutationResult } from '$lib/utils/bulkActions';
import { createResourceSelection } from '$lib/utils/resourceSelection.svelte';

export interface ImagesControllerOpts {
  token: () => string | undefined;
  projectId: () => string | undefined;
}
export interface ImageRepositoryGroup {
  repository: string;
  images: ImageInfo[];
  latest: ImageInfo;
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
  let searchQuery = $state('');
  let repositoryFilter = $state('all');
  let tagFilter = $state('all');
  let sortMode = $state<'relevance' | 'updated' | 'name'>('relevance');
  let sortOrder = $state<'asc' | 'desc'>('desc');
  let editTarget = $state<ImageInfo | null>(null);
  let showUploadModal = $state(false);
  let uploadInitialFile = $state<File | null>(null);
  let bulkActioning = $state(false);
  const selection = createResourceSelection();
  function referenceParts(image: ImageInfo): { repository: string; tag: string } {
    if (image.repository) return { repository: image.repository, tag: image.tag ?? 'latest' };
    try {
      const parsed = parseImageReference(image.name);
      return { repository: parsed.repository, tag: image.tag ?? parsed.tag };
    } catch {
      return { repository: image.name, tag: image.tag ?? 'latest' };
    }
  }

  const filteredImages = $derived.by(() => {
    let list = images.filter((img) => {
      const reference = referenceParts(img);
      if (distroFilter !== 'all') {
        if (distroFilter === 'other') {
          if (img.os_distro && KNOWN_DISTROS.includes(img.os_distro)) return false;
        } else if (img.os_distro !== distroFilter) {
          return false;
        }
      }
      if (repositoryFilter !== 'all' && reference.repository !== repositoryFilter) return false;
      if (tagFilter !== 'all' && reference.tag !== tagFilter) return false;
      return imageReferenceMatchesQuery(img, searchQuery);
    });
    list.sort((a, b) => {
      if (sortMode === 'relevance' && searchQuery.trim()) {
        const scoreDelta = imageReferenceMatchScore(b, searchQuery) - imageReferenceMatchScore(a, searchQuery);
        if (scoreDelta !== 0) return scoreDelta;
      }
      if (sortMode === 'name') {
        return referenceParts(a).repository.localeCompare(referenceParts(b).repository)
          || referenceParts(a).tag.localeCompare(referenceParts(b).tag);
      }
      const da = a.updated_at ?? a.created_at ?? '';
      const db = b.updated_at ?? b.created_at ?? '';
      const dateDelta = db.localeCompare(da);
      return dateDelta !== 0 ? dateDelta : (sortOrder === 'desc' ? b.name.localeCompare(a.name) : a.name.localeCompare(b.name));
    });
    return list;
  });
  const distroGroups = $derived.by(() => {
    const counts: Record<string, number> = { all: images.length };
    for (const image of images) {
      const distro = image.os_distro && KNOWN_DISTROS.includes(image.os_distro)
        ? image.os_distro
        : 'other';
      counts[distro] = (counts[distro] ?? 0) + 1;
    }
    return counts;
  });

  const repositoryOptions = $derived.by(() => {
    const counts = new Map<string, number>();
    for (const image of images) {
      const repository = referenceParts(image).repository;
      counts.set(repository, (counts.get(repository) ?? 0) + 1);
    }
    return [...counts.entries()]
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .map(([value, count]) => ({ value, label: value, count }));
  });

  const tagOptions = $derived.by(() => {
    const counts = new Map<string, number>();
    for (const image of images) {
      const reference = referenceParts(image);
      if (repositoryFilter !== 'all' && reference.repository !== repositoryFilter) continue;
      counts.set(reference.tag, (counts.get(reference.tag) ?? 0) + 1);
    }
    return [...counts.entries()]
      .sort((a, b) => (a[0] === 'latest' ? -1 : b[0] === 'latest' ? 1 : a[0].localeCompare(b[0])))
      .map(([value, count]) => ({ value, label: value, count }));
  });

  const visibleRepositoryCount = $derived(new Set(filteredImages.map((image) => referenceParts(image).repository)).size);

  function buildRepositoryGroups(source: ImageInfo[]): ImageRepositoryGroup[] {
    const groups = new Map<string, ImageInfo[]>();
    for (const image of source) {
      const repository = referenceParts(image).repository;
      const entries = groups.get(repository) ?? [];
      entries.push(image);
      groups.set(repository, entries);
    }
    return [...groups.entries()]
      .map(([repository, groupImages]): ImageRepositoryGroup => {
        const sortedImages = [...groupImages].sort((a, b) => {
          const da = a.updated_at ?? a.created_at ?? '';
          const db = b.updated_at ?? b.created_at ?? '';
          return db.localeCompare(da) || referenceParts(a).tag.localeCompare(referenceParts(b).tag);
        });
        return { repository, images: sortedImages, latest: sortedImages[0] };
      })
      .sort((a, b) => {
        const da = a.latest.updated_at ?? a.latest.created_at ?? '';
        const db = b.latest.updated_at ?? b.latest.created_at ?? '';
        return sortMode === 'name'
          ? a.repository.localeCompare(b.repository)
          : db.localeCompare(da) || a.repository.localeCompare(b.repository);
      });
  }

  const repositoryGroups = $derived(buildRepositoryGroups(filteredImages));
  const allRepositoryGroups = $derived(buildRepositoryGroups(images));

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
    selection.remove([id]);
  }

  function updateImage(updated: ImageInfo) {
    images = images.map(i => i.id === updated.id ? updated : i);
  }

  async function fetchImages(fetchOpts?: { refresh?: boolean }) {
    try {
      images = await api.get<ImageInfo[]>('/api/v1/images', opts.token(), opts.projectId(), fetchOpts);
      selection.retain(images.map((image) => image.id));
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
      selection.remove([id]);
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

  async function executeBulkAction(
    action: 'activate' | 'deactivate' | 'delete',
    ids: readonly string[],
  ): Promise<BulkMutationResult[]> {
    const token = opts.token();
    const projectId = opts.projectId();
    bulkActioning = true;
    try {
      const results = await executeBulkMutations(ids, (id) => {
        if (action === 'delete') return api.delete(`/api/v1/images/${id}`, token, projectId);
        const endpoint = action === 'activate' ? 'reactivate' : 'deactivate';
        return api.post(`/api/v1/images/${id}/${endpoint}`, {}, token, projectId);
      });
      if (opts.projectId() === projectId) {
        selection.remove(results.filter((result) => result.ok).map((result) => result.id));
        await fetchImages({ refresh: true });
      }
      return results;
    } finally {
      bulkActioning = false;
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
  function clearFilters() {
    searchQuery = '';
    repositoryFilter = 'all';
    tagFilter = 'all';
    distroFilter = 'all';
    sortMode = 'relevance';
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
    get bulkActioning() { return bulkActioning; },
    get selection() { return selection; },
    get distroFilter() { return distroFilter; },
    set distroFilter(v: string) { distroFilter = v; },
    get searchQuery() { return searchQuery; },
    set searchQuery(v: string) { searchQuery = v; },
    get repositoryFilter() { return repositoryFilter; },
    set repositoryFilter(v: string) { repositoryFilter = v; },
    get tagFilter() { return tagFilter; },
    set tagFilter(v: string) { tagFilter = v; },
    get sortMode() { return sortMode; },
    set sortMode(v: 'relevance' | 'updated' | 'name') { sortMode = v; },
    get sortOrder() { return sortOrder; },
    set sortOrder(v: 'asc' | 'desc') { sortOrder = v; },
    get editTarget() { return editTarget; },
    set editTarget(v: ImageInfo | null) { editTarget = v; },
    get showUploadModal() { return showUploadModal; },
    set showUploadModal(v: boolean) { showUploadModal = v; },
    get uploadInitialFile() { return uploadInitialFile; },
    get allRepositoryGroups() { return allRepositoryGroups; },
    set uploadInitialFile(v: File | null) { uploadInitialFile = v; },
    get filteredImages() { return filteredImages; },
    get distroGroups() { return distroGroups; },
    get repositoryOptions() { return repositoryOptions; },
    get tagOptions() { return tagOptions; },
    get visibleRepositoryCount() { return visibleRepositoryCount; },
    get repositoryGroups() { return repositoryGroups; },
    openImagePanel,
    closeImagePanel,
    handleImageDeleted,
    updateImage,
    fetchImages,
    deleteImage,
    toggleActivation,
    executeBulkAction,
    forceRefresh,
    clearFilters,
  };
}
