<script lang="ts">
  import { untrack } from 'svelte';
  import { auth } from '$lib/stores/auth';
  import { api, ApiError } from '$lib/api/client';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
  import PageHeader from '$lib/components/ui/PageHeader.svelte';
  import LibraryUsageChart from '$lib/components/LibraryUsageChart.svelte';
  import { buildLibraryGraph } from '$lib/utils/librariesGraph';
  import LibraryDependencyGraph from '$lib/components/admin/libraries/LibraryDependencyGraph.svelte';
  import LibraryCard from '$lib/components/admin/libraries/LibraryCard.svelte';
  import FileStorageList from '$lib/components/admin/libraries/FileStorageList.svelte';
  import type { LibraryConfig, FileStorage, TsPoint } from '$lib/types/libraries';

  let libraries = $state<LibraryConfig[]>([]);
  let fileStorages = $state<FileStorage[]>([]);
  let loading = $state(true);
  let refreshing = $state(false);
  let error = $state('');
  let message = $state('');
  let buildingId = $state<string | null>(null);
  let usageData = $state<TsPoint[]>([]);
  let usageRange = $state('7d');

  const token = $derived($auth.token ?? undefined);
  const projectId = $derived($auth.projectId ?? undefined);

  const layout = $derived(buildLibraryGraph(libraries, getBuildStatus));

  async function loadData() {
    if (libraries.length === 0) loading = true;
    else refreshing = true;
    error = '';
    await Promise.allSettled([
      api.get<LibraryConfig[]>('/api/libraries', token, projectId)
        .then(v => { libraries = v; loading = false; })
        .catch(e => { error = e instanceof ApiError ? e.message : '데이터 로드 실패'; loading = false; }),
      api.get<FileStorage[]>('/api/admin/file-storage', token, projectId)
        .then(v => { fileStorages = v; })
        .catch(() => {}),
    ]);
    loading = false;
    refreshing = false;
  }

  async function loadUsage(range: string) {
    try {
      usageData = await api.get<TsPoint[]>(`/api/admin/timeseries/library_usage?range=${range}`, token, projectId);
    } catch {
      usageData = [];
    }
  }

  $effect(() => {
    if (!token) return;
    untrack(() => {
      loadData();
      loadUsage(usageRange);
    });
  });

  function getStorageForLibrary(lib: LibraryConfig): FileStorage | null {
    return fileStorages.find(
      fs => fs.library_name === lib.id && fs.library_version === lib.version
    ) ?? null;
  }

  function getBuildStatus(lib: LibraryConfig): string {
    const fs = getStorageForLibrary(lib);
    if (!fs) return 'none';

    // union_status 메타데이터를 1순위로 판단
    const unionStatus = fs.metadata?.union_status;
    if (unionStatus) {
      if (unionStatus === 'ready') return 'ready';
      if (unionStatus === 'building' || unionStatus === 'pending') return 'building';
      if (unionStatus === 'error' || unionStatus === 'indeterminate') return 'failed';
      if (unionStatus === 'cancelled') return 'none';
    }

    // union_status 없을 때 Manila share status 폴백
    if (fs.status === 'available') return 'ready';
    if (fs.status === 'creating' || fs.status === 'extending') return 'building';
    if (fs.status === 'error') return 'failed';
    return fs.status;
  }

  async function triggerBuild(lib: LibraryConfig) {
    if (buildingId) return;
    buildingId = lib.id;
    message = '';
    error = '';
    try {
      await api.post(`/api/admin/file-storage/build?library_id=${encodeURIComponent(lib.id)}&auto_install=true`, {}, token, projectId);
      message = `${lib.name} 빌드를 시작했습니다.`;
      await loadData();
    } catch (e) {
      if (e instanceof ApiError) {
        if (e.status === 409) {
          error = `${lib.name}: 이미 빌드된 파일 스토리지가 존재합니다. 재빌드하려면 기존 스토리지를 삭제 후 다시 시도하세요.`;
        } else if (e.status === 400) {
          error = `${lib.name} 빌드 설정 오류: ${e.message}`;
        } else if (e.status === 404) {
          error = `${lib.name}: 라이브러리를 찾을 수 없습니다.`;
        } else {
          error = `${lib.name} 빌드 실패 (${e.status}): ${e.message}`;
        }
      } else {
        error = `${lib.name} 빌드 트리거 실패: 네트워크 오류가 발생했습니다.`;
      }
    } finally {
      buildingId = null;
    }
  }

  function scrollToCard(id: string) {
    document.getElementById(`lib-card-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
</script>

<div class="flex flex-col h-full overflow-auto bg-gray-900 text-gray-100 p-6">
  <PageHeader title="라이브러리 관리" breadcrumb="라이브러리">
    {#snippet actions()}
      <div class="flex items-center gap-2">
        <button onclick={loadData} class="text-xs text-gray-400 hover:text-white transition-colors px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600 flex items-center gap-1.5">새로고침</button>
      </div>
    {/snippet}
  </PageHeader>

  {#if error}
    <div class="mb-4 p-3 bg-red-900/40 border border-red-700 rounded-md text-red-300 text-sm">{error}</div>
  {/if}
  {#if message}
    <div class="mb-4 p-3 bg-green-900/40 border border-green-700 rounded-md text-green-300 text-sm">{message}</div>
  {/if}

  <div class="mb-6">
    <LibraryUsageChart
      data={usageData}
      title="라이브러리 사용 현황 (활성 VM 기준)"
      currentRange={usageRange}
      onRangeChange={(r) => { usageRange = r; loadUsage(r); }}
    />
  </div>

  {#if loading}
    <LoadingSkeleton rows={6} />
  {:else if libraries.length === 0}
    <div class="flex flex-col items-center justify-center flex-1 text-gray-500">
      <p>등록된 라이브러리가 없습니다</p>
    </div>
  {:else}
    <div class:opacity-60={refreshing} class:pointer-events-none={refreshing}>
      <div class="mb-6">
        <LibraryDependencyGraph {layout} onNodeClick={scrollToCard} />
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {#each libraries as lib}
          {@const buildStatus = getBuildStatus(lib)}
          {@const latestMount = usageData.length > 0 ? usageData[usageData.length - 1]?.[lib.name] : undefined}
          <LibraryCard
            {lib}
            {buildStatus}
            {latestMount}
            isBuilding={buildingId === lib.id}
            onTriggerBuild={triggerBuild}
          />
        {/each}
      </div>

      {#if fileStorages.length > 0}
        <FileStorageList {fileStorages} />
      {/if}
    </div>
  {/if}
</div>
