<script lang="ts">
  import { untrack } from 'svelte';
  import { auth } from '$lib/stores/auth';
  import { api, ApiError } from '$lib/api/client';
  import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
  import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
  import ImageDetailPanel from '$lib/components/ImageDetailPanel.svelte';
  import ImageUploadModal from '$lib/components/ImageUploadModal.svelte';
  import SlidePanel from '$lib/components/SlidePanel.svelte';
  import PageHeader from '$lib/components/ui/PageHeader.svelte';
  import type { ImageInfo } from '$lib/types/resources';
  import { KNOWN_DISTROS } from '$lib/utils/imageOs';
  import ImageDistroFilter from '$lib/components/dashboard/images/ImageDistroFilter.svelte';
  import ImageCard from '$lib/components/dashboard/images/ImageCard.svelte';
  import ImageEditModal from '$lib/components/dashboard/images/ImageEditModal.svelte';
  import ImageDropOverlay from '$lib/components/dashboard/images/ImageDropOverlay.svelte';

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

  async function fetchImages(opts?: { refresh?: boolean }) {
    try {
      images = await api.get<ImageInfo[]>('/api/images', $auth.token ?? undefined, $auth.projectId ?? undefined, opts);
      error = '';
    } catch (e) {
      error = e instanceof ApiError ? `조회 실패 (${e.status})` : '서버 오류';
    } finally {
      loading = false;
    }
  }

  async function deleteImage(id: string, name: string) {
    if (!confirm(`이미지 "${name}"을 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.`)) return;
    deleting = id;
    try {
      await api.delete(`/api/images/${id}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
      images = images.filter(img => img.id !== id);
    } catch (e) {
      alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
    } finally {
      deleting = null;
    }
  }

  async function toggleActivation(img: ImageInfo) {
    togglingId = img.id;
    try {
      const action = img.status === 'active' ? 'deactivate' : 'reactivate';
      await api.post(`/api/images/${img.id}/${action}`, {}, $auth.token ?? undefined, $auth.projectId ?? undefined);
      await fetchImages({ refresh: true });
    } catch (e) {
      alert('상태 변경 실패: ' + (e instanceof ApiError ? e.message : String(e)));
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

  const ar = createAutoRefresh(() => fetchImages(), {
    storageKey: 'dashboard-compute-images',
    defaultActive: true,
    defaultInterval: 60,
    intervalOptions: [10, 15, 30, 60],
  });

  $effect(() => {
    const pid = $auth.projectId;
    if (!pid) return;
    untrack(() => fetchImages());
  });
</script>

<ImageEditModal
  target={editTarget}
  onClose={() => editTarget = null}
  onSaved={(updated) => { images = images.map(i => i.id === updated.id ? updated : i); }}
/>

<ImageDropOverlay onFile={(f) => { uploadInitialFile = f; showUploadModal = true; }} />

<div class="p-4 md:p-8">
  <PageHeader breadcrumb="COMPUTE / IMAGES" title="이미지">
    {#snippet actions()}
      <AutoRefreshControl
        bind:active={ar.active}
        bind:intervalSeconds={ar.intervalSeconds}
        intervalOptions={ar.intervalOptions}
        refreshing={refreshing}
        onManualRefresh={forceRefresh}
      />
      <button
        onclick={() => sortOrder = sortOrder === 'desc' ? 'asc' : 'desc'}
        class="flex items-center gap-1.5 text-xs text-gray-400 hover:text-white px-3 py-1.5 rounded-lg border border-gray-700 hover:border-gray-600 transition-colors"
      >
        날짜 {sortOrder === 'desc' ? '↓ 최신순' : '↑ 오래된순'}
      </button>
      <button
        onclick={() => { uploadInitialFile = null; showUploadModal = true; }}
        class="flex items-center gap-1.5 text-xs text-white px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 transition-colors font-medium"
      >
        + 이미지 업로드
      </button>
    {/snippet}
  </PageHeader>

  {#if error}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>{/if}

  {#if loading}
    <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3.5">
      {#each Array(8) as _}
        <div class="animate-pulse h-32 bg-gray-900 border border-gray-800 rounded-2xl"></div>
      {/each}
    </div>
  {:else}
    <ImageDistroFilter bind:distroFilter counts={distroGroups} />

    {#if filteredImages.length === 0}
      <div class="text-center py-20 text-gray-600">
        <p class="text-lg">이미지가 없습니다</p>
      </div>
    {:else}
      <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3.5">
        {#each filteredImages as img (img.id)}
          <ImageCard
            {img}
            isOwner={img.owner === $auth.projectId}
            toggling={togglingId === img.id}
            deleting={deleting === img.id}
            onSelect={openImagePanel}
            onToggleActivation={toggleActivation}
            onEdit={(i) => editTarget = i}
            onDelete={deleteImage}
          />
        {/each}
      </div>
    {/if}
  {/if}
</div>

<ImageUploadModal
  bind:open={showUploadModal}
  token={$auth.token ?? undefined}
  projectId={$auth.projectId ?? undefined}
  initialFile={uploadInitialFile}
  onUploaded={() => fetchImages({ refresh: true })}
  onClose={() => { uploadInitialFile = null; }}
/>

{#if selectedImageId}
  <SlidePanel onClose={closeImagePanel} width="w-full md:w-[60vw] max-w-2xl">
    <ImageDetailPanel
      imageId={selectedImageId}
      onClose={closeImagePanel}
      onDelete={handleImageDeleted}
    />
  </SlidePanel>
{/if}
