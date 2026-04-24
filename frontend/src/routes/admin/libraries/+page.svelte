<script lang="ts">
  import { auth } from '$lib/stores/auth';
  import { api, ApiError } from '$lib/api/client';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
  import RefreshButton from '$lib/components/RefreshButton.svelte';
  import AutoRefreshToggle from '$lib/components/AutoRefreshToggle.svelte';
  import StatusChip from '$lib/components/ui/StatusChip.svelte';
  import PageHeader from '$lib/components/ui/PageHeader.svelte';

  interface LibraryConfig {
    id: string;
    name: string;
    version: string;
    packages: string[];
    depends_on: string[];
    available_prebuilt: boolean;
    share_proto: string;
  }

  interface FileStorage {
    id: string;
    name: string;
    status: string;
    library_name: string | null;
    library_version: string | null;
    metadata: Record<string, string>;
  }

  let libraries = $state<LibraryConfig[]>([]);
  let fileStorages = $state<FileStorage[]>([]);
  let loading = $state(true);
  let error = $state('');
  let message = $state('');
  let buildingId = $state<string | null>(null);
  let autoRefresh = $state(false);

  const token = $derived($auth.token ?? undefined);
  const projectId = $derived($auth.projectId ?? undefined);

  async function loadData() {
    loading = true;
    error = '';
    try {
      [libraries, fileStorages] = await Promise.all([
        api.get<LibraryConfig[]>('/api/libraries', token, projectId),
        api.get<FileStorage[]>('/api/admin/file-storage', token, projectId),
      ]);
    } catch (e) {
      error = e instanceof ApiError ? e.message : '데이터 로드 실패';
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    if (token) loadData();
  });

  // 라이브러리에 해당하는 FileStorage 찾기
  function getStorageForLibrary(lib: LibraryConfig): FileStorage | null {
    return fileStorages.find(
      fs => fs.library_name === lib.name && fs.library_version === lib.version
    ) ?? null;
  }

  // 빌드 상태 계산
  function getBuildStatus(lib: LibraryConfig): string {
    const fs = getStorageForLibrary(lib);
    if (!fs) return 'none';
    const unionStatus = fs.metadata?.union_status ?? fs.status;
    if (unionStatus === 'available' || fs.status === 'available') return 'ready';
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
      error = e instanceof ApiError ? e.message : '빌드 트리거 실패';
    } finally {
      buildingId = null;
    }
  }

  // 빌드 상태에 따른 StatusChip 색상 매핑
  function statusLabel(status: string): string {
    const map: Record<string, string> = {
      ready: 'ready',
      building: 'building',
      failed: 'error',
      none: 'none',
    };
    return map[status] ?? status;
  }

  function statusText(status: string): string {
    const map: Record<string, string> = {
      ready: '빌드 완료',
      building: '빌드 중',
      failed: '빌드 실패',
      none: '미빌드',
    };
    return map[status] ?? status;
  }
</script>

<div class="flex flex-col h-full overflow-auto bg-gray-900 text-gray-100 p-6">
  <PageHeader title="라이브러리 관리" breadcrumb="라이브러리">
    {#snippet action()}
      <div class="flex items-center gap-2">
        <AutoRefreshToggle bind:enabled={autoRefresh} interval={10000} onTick={loadData} />
        <RefreshButton onclick={loadData} />
      </div>
    {/snippet}
  </PageHeader>

  {#if error}
    <div class="mb-4 p-3 bg-red-900/40 border border-red-700 rounded-md text-red-300 text-sm">{error}</div>
  {/if}
  {#if message}
    <div class="mb-4 p-3 bg-green-900/40 border border-green-700 rounded-md text-green-300 text-sm">{message}</div>
  {/if}

  {#if loading}
    <LoadingSkeleton rows={6} />
  {:else if libraries.length === 0}
    <div class="flex flex-col items-center justify-center flex-1 text-gray-500">
      <p>등록된 라이브러리가 없습니다</p>
    </div>
  {:else}
    <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      {#each libraries as lib}
        {@const buildStatus = getBuildStatus(lib)}
        <div class="bg-gray-800 rounded-lg border border-gray-700 p-5 flex flex-col gap-4">
          <div class="flex items-start justify-between">
            <div>
              <h3 class="font-semibold text-gray-100">{lib.name}</h3>
              <p class="text-xs text-gray-500 mt-0.5">v{lib.version}</p>
            </div>
            <div class="flex flex-col items-end gap-1">
              <StatusChip status={statusLabel(buildStatus)} label={statusText(buildStatus)} />
              <span class="text-xs text-gray-600">{lib.share_proto ?? 'CEPHFS'}</span>
            </div>
          </div>

          {#if lib.depends_on && lib.depends_on.length > 0}
            <div>
              <p class="text-xs text-gray-500 mb-1.5">의존성</p>
              <div class="flex flex-wrap gap-1">
                {#each lib.depends_on as dep}
                  <span class="px-2 py-0.5 text-xs bg-gray-700 text-gray-300 rounded-full">{dep}</span>
                {/each}
              </div>
            </div>
          {/if}

          {#if lib.packages && lib.packages.length > 0}
            <div>
              <p class="text-xs text-gray-500 mb-1.5">패키지 ({lib.packages.length})</p>
              <div class="flex flex-wrap gap-1">
                {#each lib.packages.slice(0, 5) as pkg}
                  <span class="px-2 py-0.5 text-xs bg-gray-700/50 text-gray-400 rounded">{pkg}</span>
                {/each}
                {#if lib.packages.length > 5}
                  <span class="px-2 py-0.5 text-xs text-gray-600">+{lib.packages.length - 5}개</span>
                {/if}
              </div>
            </div>
          {/if}

          <div class="mt-auto pt-3 border-t border-gray-700">
            <button
              onclick={() => triggerBuild(lib)}
              disabled={buildingId === lib.id || buildStatus === 'building'}
              class="w-full py-1.5 text-sm bg-blue-700 hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed rounded-md transition-colors"
            >
              {buildingId === lib.id ? '요청 중...' : buildStatus === 'building' ? '빌드 중...' : buildStatus === 'ready' ? '재빌드' : '빌드 시작'}
            </button>
          </div>
        </div>
      {/each}
    </div>

    <!-- 전체 FileStorage 목록 (관리자 확인용) -->
    {#if fileStorages.length > 0}
      <div class="mt-8">
        <h2 class="text-sm font-medium text-gray-400 mb-3">프리빌트 Share 목록 ({fileStorages.length})</h2>
        <div class="rounded-lg border border-gray-700 overflow-hidden">
          <table class="w-full text-sm">
            <thead class="bg-gray-800 text-gray-400 text-xs uppercase">
              <tr>
                <th class="px-4 py-3 text-left">이름</th>
                <th class="px-4 py-3 text-left">라이브러리</th>
                <th class="px-4 py-3 text-left">상태</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-700/50">
              {#each fileStorages as fs}
                <tr class="hover:bg-gray-800/50">
                  <td class="px-4 py-3 text-gray-300 text-xs font-mono">{fs.name}</td>
                  <td class="px-4 py-3 text-gray-400 text-xs">
                    {fs.library_name ?? '-'}
                    {#if fs.library_version}<span class="text-gray-600"> v{fs.library_version}</span>{/if}
                  </td>
                  <td class="px-4 py-3"><StatusChip status={fs.status} /></td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    {/if}
  {/if}
</div>
