<script lang="ts">
  import { untrack } from 'svelte';
  import { auth } from '$lib/stores/auth';
  import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
  import { createImagesController } from '$lib/stores/imagesController.svelte';
  import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
  import ImageDetailPanel from '$lib/components/ImageDetailPanel.svelte';
  import ImageUploadModal from '$lib/components/ImageUploadModal.svelte';
  import SlidePanel from '$lib/components/SlidePanel.svelte';
  import PageHeader from '$lib/components/ui/PageHeader.svelte';
  import ImageDistroFilter from '$lib/components/dashboard/images/ImageDistroFilter.svelte';
  import ImageCard from '$lib/components/dashboard/images/ImageCard.svelte';
  import ImageEditModal from '$lib/components/dashboard/images/ImageEditModal.svelte';
  import ImageDropOverlay from '$lib/components/dashboard/images/ImageDropOverlay.svelte';

  const ctrl = createImagesController({
    token: () => $auth.token ?? undefined,
    projectId: () => $auth.projectId ?? undefined,
  });

  const ar = createAutoRefresh(() => ctrl.fetchImages(), {
    storageKey: 'dashboard-compute-images',
    defaultActive: true,
    defaultInterval: 60,
    intervalOptions: [10, 15, 30, 60],
  });

  $effect(() => {
    const pid = $auth.projectId;
    if (!pid) return;
    ctrl.loading = true;
    untrack(() => ctrl.fetchImages());
  });
</script>

<ImageEditModal
  target={ctrl.editTarget}
  onClose={() => ctrl.editTarget = null}
  onSaved={(updated) => ctrl.updateImage(updated)}
/>

<ImageDropOverlay onFile={(f) => { ctrl.uploadInitialFile = f; ctrl.showUploadModal = true; }} />

<div class="p-4 md:p-8">
  <PageHeader breadcrumb="COMPUTE / IMAGES" title="이미지">
    {#snippet actions()}
      <AutoRefreshControl
        bind:active={ar.active}
        bind:intervalSeconds={ar.intervalSeconds}
        intervalOptions={ar.intervalOptions}
        refreshing={ctrl.refreshing}
        onManualRefresh={ctrl.forceRefresh}
      />
      <button
        onclick={() => ctrl.sortOrder = ctrl.sortOrder === 'desc' ? 'asc' : 'desc'}
        class="flex items-center gap-1.5 text-xs text-gray-400 hover:text-white px-3 py-1.5 rounded-lg border border-gray-700 hover:border-gray-600 transition-colors"
      >
        날짜 {ctrl.sortOrder === 'desc' ? '↓ 최신순' : '↑ 오래된순'}
      </button>
      <button
        onclick={() => { ctrl.uploadInitialFile = null; ctrl.showUploadModal = true; }}
        class="flex items-center gap-1.5 text-xs text-white px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 transition-colors font-medium"
      >
        + 이미지 업로드
      </button>
    {/snippet}
  </PageHeader>

  {#if ctrl.error}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{ctrl.error}</div>{/if}

  {#if ctrl.loading}
    <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3.5">
      {#each Array(8) as _}
        <div class="animate-pulse h-32 bg-gray-900 border border-gray-800 rounded-2xl"></div>
      {/each}
    </div>
  {:else}
    <ImageDistroFilter bind:distroFilter={ctrl.distroFilter} counts={ctrl.distroGroups} />

    {#if ctrl.filteredImages.length === 0}
      <div class="text-center py-20 text-gray-600">
        <p class="text-lg">이미지가 없습니다</p>
      </div>
    {:else}
      <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3.5">
        {#each ctrl.filteredImages as img (img.id)}
          <ImageCard
            {img}
            isOwner={img.owner === $auth.projectId}
            toggling={ctrl.togglingId === img.id}
            deleting={ctrl.deleting === img.id}
            onSelect={ctrl.openImagePanel}
            onToggleActivation={ctrl.toggleActivation}
            onEdit={(i) => ctrl.editTarget = i}
            onDelete={ctrl.deleteImage}
          />
        {/each}
      </div>
    {/if}
  {/if}
</div>

<ImageUploadModal
  bind:open={ctrl.showUploadModal}
  token={$auth.token ?? undefined}
  projectId={$auth.projectId ?? undefined}
  initialFile={ctrl.uploadInitialFile}
  onUploaded={() => ctrl.fetchImages({ refresh: true })}
  onClose={() => { ctrl.uploadInitialFile = null; }}
/>

{#if ctrl.selectedImageId}
  <SlidePanel onClose={ctrl.closeImagePanel} width="w-full md:w-[60vw] max-w-2xl">
    <ImageDetailPanel
      imageId={ctrl.selectedImageId}
      onClose={ctrl.closeImagePanel}
      onDelete={ctrl.handleImageDeleted}
    />
  </SlidePanel>
{/if}
