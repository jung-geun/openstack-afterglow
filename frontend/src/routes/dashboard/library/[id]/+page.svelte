<script lang="ts">
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { auth, isAdmin } from '$lib/stores/auth';
  import { api, ApiError } from '$lib/api/client';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
  import PageHeader from '$lib/components/ui/PageHeader.svelte';
  import type { LayerInfo, AncestorChain } from '$lib/types/layer';
  import LayerInfoCard from '$lib/components/dashboard/library/id/LayerInfoCard.svelte';
  import LayerPackagesAccordion from '$lib/components/dashboard/library/id/LayerPackagesAccordion.svelte';
  import LayerRecipeAccordion from '$lib/components/dashboard/library/id/LayerRecipeAccordion.svelte';
  import LayerAncestorChain from '$lib/components/dashboard/library/id/LayerAncestorChain.svelte';
  import LayerDependents from '$lib/components/dashboard/library/id/LayerDependents.svelte';

  const layerId = $derived($page.params.id);
  const encodedId = $derived(encodeURIComponent(layerId));

  let layer = $state<LayerInfo | null>(null);
  let ancestors = $state<LayerInfo[]>([]);
  let dependents = $state<LayerInfo[]>([]);
  let loading = $state(true);
  let error = $state('');
  let sealing = $state(false);
  let deleting = $state(false);

  const token = $derived($auth.token ?? undefined);
  const projectId = $derived($auth.projectId ?? undefined);

  async function loadData() {
    loading = true;
    error = '';
    await Promise.allSettled([
      api.get<LayerInfo>(`/api/union/layers/${encodedId}`, token, projectId)
        .then(v => { layer = v; loading = false; })
        .catch(e => { error = e instanceof ApiError ? e.message : '레이어 로드 실패'; loading = false; }),
      api.get<AncestorChain>(`/api/union/layers/${encodedId}/ancestors`, token, projectId)
        .then(v => { ancestors = v.layers; })
        .catch(() => {}),
      api.get<LayerInfo[]>(`/api/union/layers/${encodedId}/dependents`, token, projectId)
        .then(v => { dependents = v; })
        .catch(() => {}),
    ]);
    loading = false;
  }

  $effect(() => {
    if (token && layerId) loadData();
  });

  async function sealLayer() {
    if (!layer || sealing) return;
    sealing = true;
    try {
      await api.post(`/api/union/layers/${encodedId}/seal`, {}, token, projectId);
      layer = { ...layer, sealed: true };
    } catch (e) {
      error = e instanceof ApiError ? e.message : '봉인 실패';
    } finally {
      sealing = false;
    }
  }

  async function deleteLayer() {
    if (!layer || deleting) return;
    deleting = true;
    try {
      await api.delete(`/api/union/layers/${encodedId}`, token, projectId);
      goto('/dashboard/library');
    } catch (e) {
      error = e instanceof ApiError ? e.message : '삭제 실패';
    } finally {
      deleting = false;
    }
  }
</script>

<div class="flex flex-col h-full overflow-auto bg-gray-900 text-gray-100 p-6">
  <PageHeader title={layer?.name ?? '레이어 상세'} breadcrumb="라이브러리">
    {#snippet actions()}
      <a href="/dashboard/library" class="text-sm text-gray-400 hover:text-gray-200">← 목록으로</a>
    {/snippet}
  </PageHeader>

  {#if error}
    <div class="mb-4 p-3 bg-red-900/40 border border-red-700 rounded-md text-red-300 text-sm">{error}</div>
  {/if}

  {#if loading}
    <LoadingSkeleton rows={6} />
  {:else if layer}
    <div class="grid grid-cols-1 xl:grid-cols-3 gap-6">
      <!-- 레이어 정보 -->
      <div class="xl:col-span-2 space-y-6">
        <LayerInfoCard
          {layer}
          isAdmin={$isAdmin}
          {sealing}
          {deleting}
          onSeal={sealLayer}
          onDelete={deleteLayer}
        />
        <LayerPackagesAccordion packages={layer.installed_packages} />
        <LayerRecipeAccordion recipe={layer.build_recipe} />
      </div>

      <!-- 우측: 조상 체인 + 자식 레이어 -->
      <div class="space-y-6">
        <LayerAncestorChain {ancestors} currentLayerId={layerId} />
        <LayerDependents {dependents} />
      </div>
    </div>
  {:else}
    <p class="text-gray-400">레이어를 찾을 수 없습니다.</p>
  {/if}
</div>
