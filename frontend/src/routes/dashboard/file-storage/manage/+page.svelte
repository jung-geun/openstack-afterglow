<script lang="ts">
  import { untrack } from 'svelte';
  import { auth } from '$lib/stores/auth';
  import { api, ApiError } from '$lib/api/client';
  import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
  import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
  import StatusChip from '$lib/components/ui/StatusChip.svelte';
  import PageHeader from '$lib/components/ui/PageHeader.svelte';

  interface FileStorage {
    id: string;
    name: string;
    status: string;
    size: number;
    library_name: string | null;
    library_version: string | null;
    built_at: string | null;
    metadata: Record<string, string>;
  }

  interface LibraryConfig {
    id: string;
    name: string;
    version: string;
    available_prebuilt: boolean;
  }


  let fileStorages = $state<FileStorage[]>([]);
  let libraries = $state<LibraryConfig[]>([]);
  let building = $state<string | null>(null);
  let loading = $state(true);
  let refreshing = $state(false);
  let error = $state('');
  let message = $state('');
  let autoInstall = $state(true);

  const token = $derived($auth.token ?? undefined);
  const projectId = $derived($auth.projectId ?? undefined);

  async function loadData() {
    if (fileStorages.length === 0) loading = true;
    else refreshing = true;
    await Promise.allSettled([
      api.get<FileStorage[]>('/api/admin/file-storage', token, projectId)
        .then(v => { fileStorages = v; loading = false; })
        .catch(e => {
          error = e instanceof ApiError ? `로드 실패: ${e.message}` : '서버 오류';
          fileStorages = [];
          loading = false;
        }),
      api.get<LibraryConfig[]>('/api/libraries', token, projectId)
        .then(v => { libraries = v; })
        .catch(() => {}),
    ]);
    loading = false;
    refreshing = false;
  }

  async function buildFileStorage(libId: string) {
    building = libId;
    message = '';
    error = '';
    try {
      const params = new URLSearchParams({ library_id: libId });
      if (autoInstall) params.set('auto_install', 'true');
      const res = await api.post<{ file_storage_id: string; server_id?: string }>(
        `/api/admin/file-storage/build?${params}`, {}, token, projectId
      );
      if (autoInstall && res.server_id) {
        message = `자동 빌드 시작됨 (Share: ${res.file_storage_id}, VM: ${res.server_id})`;
      } else {
        message = `파일 스토리지 생성 시작됨 (ID: ${res.file_storage_id})`;
      }
      await loadData();
    } catch (e) {
      error = e instanceof ApiError ? `빌드 실패: ${e.message}` : '서버 오류';
    } finally {
      building = null;
    }
  }

  $effect(() => {
    if (!$auth.projectId) return;
    fileStorages = [];
    untrack(() => loadData());
  });

  const ar = createAutoRefresh(loadData, {
    storageKey: 'dashboard-file-storage',
    defaultActive: true,
    defaultInterval: 30,
    intervalOptions: [15, 30, 60]
  });
</script>

<div class="p-4 md:p-8 max-w-7xl mx-auto">
  <PageHeader breadcrumb="FILE STORAGE / MANAGE" title="라이브러리 관리" subtitle="Strategy A (사전 빌드)에서 사용할 Manila CephFS 파일 스토리지를 관리합니다.">
    {#snippet actions()}
      <label class="flex items-center gap-2 text-xs text-gray-400 cursor-pointer">
        <input type="checkbox" bind:checked={autoInstall} class="rounded border-gray-600 bg-gray-800 text-blue-500 focus:ring-blue-500 focus:ring-offset-0" />
        자동 패키지 설치
      </label>
      <AutoRefreshControl
        bind:active={ar.active}
        bind:intervalSeconds={ar.intervalSeconds}
        intervalOptions={ar.intervalOptions}
        refreshing={loading || refreshing}
        onManualRefresh={loadData}
      />
    {/snippet}
  </PageHeader>

  {#if error}
    <div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>
  {/if}
  {#if message}
    <div class="bg-green-900/40 border border-green-700 text-green-300 rounded-lg px-4 py-3 text-sm mb-4">{message}</div>
  {/if}

  {#if loading}
    <LoadingSkeleton variant="list" rows={4} />
  {:else}
    <div class:opacity-60={refreshing} class:pointer-events-none={refreshing}>
    <div class="mb-8">
      <h2 class="text-base font-semibold text-white mb-3">사전 빌드 상태</h2>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {#each libraries as lib}
          {@const prebuilt = fileStorages.find(s => s.library_name === lib.id && s.metadata?.union_type === 'prebuilt')}
          <div class="bg-gray-900 border border-gray-700 rounded-xl p-4">
            <div class="flex items-start justify-between mb-2">
              <div>
                <div class="font-medium text-white text-sm">{lib.name}</div>
                <div class="text-xs text-gray-500">v{lib.version}</div>
              </div>
              {#if prebuilt}
                <StatusChip status={prebuilt.status} />
              {:else}
                <span class="text-xs text-gray-600">미구축</span>
              {/if}
            </div>
            {#if prebuilt}
              <div class="text-xs text-gray-600 mb-3">
                File Storage ID: <span class="font-mono">{prebuilt.id.slice(0, 8)}...</span>
                {#if prebuilt.built_at}• {prebuilt.built_at.split('T')[0]}{/if}
              </div>
            {/if}
            <button
              onclick={() => buildFileStorage(lib.id)}
              disabled={building === lib.id || !!prebuilt}
              class="w-full text-xs py-1.5 rounded-lg border transition-colors {prebuilt ? 'border-gray-700 text-gray-600 cursor-not-allowed' : 'border-blue-700 text-blue-400 hover:bg-blue-900/20'}"
            >
              {building === lib.id ? '생성 중...' : prebuilt ? '구축됨' : '파일 스토리지 생성'}
            </button>
          </div>
        {/each}
        {#if libraries.length === 0}
          <div class="col-span-2 text-gray-600 text-sm">라이브러리 정보를 불러올 수 없습니다</div>
        {/if}
      </div>
    </div>

    <div class="flex items-center justify-between mb-3">
      <h2 class="text-base font-semibold text-white">전체 파일 스토리지 목록</h2>
    </div>
    {#if fileStorages.length === 0}
      <div class="text-gray-600 text-sm py-8 text-center">파일 스토리지가 없습니다</div>
    {:else}
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {#each fileStorages as fs}
          <div class="bg-gray-900 border border-gray-800 rounded-2xl p-5">
            <!-- 헤더 -->
            <div class="flex items-center gap-2.5 mb-3">
              <div class="w-10 h-10 rounded-[10px] bg-teal-500/15 border border-teal-500/30 text-teal-400 flex items-center justify-center shrink-0">
                <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"/>
                </svg>
              </div>
              <div class="flex-1 min-w-0">
                <div class="text-white font-semibold text-sm font-mono truncate">{fs.name}</div>
                <div class="flex items-center gap-1.5 mt-0.5">
                  {#if fs.metadata?.union_type}
                    <span class="text-[10px] px-1.5 py-0.5 rounded bg-blue-900/40 text-blue-300 border border-blue-800/50">{fs.metadata.union_type}</span>
                  {/if}
                  {#if fs.library_name}
                    <span class="text-[10px] px-1.5 py-0.5 rounded bg-violet-900/40 text-violet-300 border border-violet-800/50 truncate">{fs.library_name}</span>
                  {/if}
                </div>
              </div>
            </div>
            <!-- 정보 -->
            <div class="grid grid-cols-2 gap-2 mb-3">
              <div>
                <div class="text-[11px] uppercase tracking-wider font-medium text-gray-500">크기</div>
                <div class="text-white font-mono text-sm mt-0.5">{fs.size} GB</div>
              </div>
              <div>
                <div class="text-[11px] uppercase tracking-wider font-medium text-gray-500">상태</div>
                <div class="mt-0.5"><StatusChip status={fs.status} /></div>
              </div>
            </div>
            <!-- 빌드 날짜 -->
            {#if fs.built_at}
              <div class="pt-3 border-t border-gray-800">
                <div class="text-[11px] text-gray-500">빌드: {fs.built_at.split('T')[0]}</div>
              </div>
            {/if}
          </div>
        {/each}
      </div>
    {/if}
    </div>
  {/if}
</div>
