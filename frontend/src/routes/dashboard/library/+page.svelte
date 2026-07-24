<script lang="ts">
  import { auth, isAdmin } from '$lib/stores/auth';
  import { api, ApiError } from '$lib/api/client';
  import type { LayerInfo } from '$lib/types/layer';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
  import PageHeader from '$lib/components/ui/PageHeader.svelte';
  import LayerSearchBar from '$lib/components/library/LayerSearchBar.svelte';
  import LayerCatalogTable from '$lib/components/library/LayerCatalogTable.svelte';

  let layers = $state<LayerInfo[]>([]);
  let loading = $state(true);
  let refreshing = $state(false);
  let error = $state('');
  let nameFilter = $state('');
  let currentPage = $state(0);
  const pageSize = 50;

  const token = $derived($auth.token ?? undefined);
  const projectId = $derived($auth.projectId ?? undefined);

  let initialLoaded = false;
  let loadGeneration = 0;
  let loadController: AbortController | null = null;
  let searchTimer: ReturnType<typeof setTimeout> | null = null;

  async function loadLayers(opts?: { refresh?: boolean }) {
    if (searchTimer) {
      clearTimeout(searchTimer);
      searchTimer = null;
    }
    loadController?.abort();
    const controller = new AbortController();
    loadController = controller;
    const requestToken = token;
    const requestProjectId = projectId;
    const requestFilter = nameFilter;
    const requestPage = currentPage;
    const generation = ++loadGeneration;
    if (!initialLoaded) loading = true;
    else refreshing = true;
    error = '';
    try {
      const params = new URLSearchParams({ limit: String(pageSize), offset: String(requestPage * pageSize) });
      if (requestFilter) params.set('name', requestFilter);
      const value = await api.get<LayerInfo[]>(
        `/api/v1/union/layers?${params}`,
        requestToken,
        requestProjectId,
        { refresh: opts?.refresh, signal: controller.signal },
      );
      if (
        generation !== loadGeneration
        || token !== requestToken
        || projectId !== requestProjectId
        || nameFilter !== requestFilter
        || currentPage !== requestPage
      ) return;
      layers = value;
      initialLoaded = true;
    } catch (e) {
      if (
        generation === loadGeneration
        && token === requestToken
        && projectId === requestProjectId
        && !(e instanceof DOMException && e.name === 'AbortError')
      ) {
        error = e instanceof ApiError ? e.message : '레이어 로드 실패';
        if (!initialLoaded) layers = [];
      }
    } finally {
      if (generation === loadGeneration && token === requestToken && projectId === requestProjectId) {
        loading = false;
        refreshing = false;
      }
    }
  }

  $effect(() => {
    const requestToken = token;
    void projectId;
    void nameFilter;
    if (!requestToken) return;
    currentPage = 0;
    loadGeneration += 1;
    loadController?.abort();
    if (searchTimer) clearTimeout(searchTimer);
    searchTimer = setTimeout(() => void loadLayers(), 250);
    return () => {
      if (searchTimer) clearTimeout(searchTimer);
      loadController?.abort();
    };
  });

  function handleSearch() {
    currentPage = 0;
    void loadLayers();
  }
</script>

<div class="flex flex-col h-full overflow-auto bg-gray-900 text-gray-100 p-6">
  <PageHeader title="레이어 카탈로그" breadcrumb="라이브러리">
    {#snippet actions()}
      <div class="flex items-center gap-2">
        {#if $isAdmin}
          <a
            href="/dashboard/library/create"
            class="px-3 py-1.5 text-sm bg-blue-600 hover:bg-blue-500 rounded-md transition-colors"
          >+ 새 레이어</a>
        {/if}
        <a
          href="/dashboard/library/templates"
          class="px-3 py-1.5 text-sm bg-gray-700 hover:bg-gray-600 rounded-md transition-colors"
        >템플릿</a>
        <button onclick={() => loadLayers({ refresh: true })} class="text-xs text-gray-400 hover:text-white transition-colors px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600 flex items-center gap-1.5">새로고침</button>
      </div>
    {/snippet}
  </PageHeader>

  <LayerSearchBar bind:query={nameFilter} onSearch={handleSearch} />

  {#if error}
    <div class="mb-4 p-3 bg-red-900/40 border border-red-700 rounded-md text-red-300 text-sm">{error}</div>
  {/if}

  {#if loading}
    <LoadingSkeleton rows={8} />
  {:else if layers.length === 0}
    <div class="flex flex-col items-center justify-center flex-1 text-gray-500">
      <svg class="w-12 h-12 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
      </svg>
      <p>레이어가 없습니다</p>
    </div>
  {:else}
    <LayerCatalogTable
      {layers}
      query={nameFilter}
      {refreshing}
      {currentPage}
      {pageSize}
      onPrev={() => { currentPage = Math.max(0, currentPage - 1); void loadLayers(); }}
      onNext={() => { currentPage++; void loadLayers(); }}
    />
  {/if}
</div>
