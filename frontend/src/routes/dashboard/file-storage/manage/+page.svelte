<script lang="ts">
  import { untrack } from 'svelte';
  import { auth } from '$lib/stores/auth';
  import { api, ApiError } from '$lib/api/client';
  import AutoRefreshToggle from '$lib/components/AutoRefreshToggle.svelte';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';

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

  const statusColor: Record<string, string> = {
    available: 'text-green-400',
    creating:  'text-yellow-400',
    building:  'text-yellow-400',
    deleting:  'text-orange-400',
    error:     'text-red-400',
  };

  let fileStorages = $state<FileStorage[]>([]);
  let libraries = $state<LibraryConfig[]>([]);
  let building = $state<string | null>(null);
  let loading = $state(true);
  let error = $state('');
  let message = $state('');
  let autoInstall = $state(true);
  let autoRefresh = $state(false);

  const token = $derived($auth.token ?? undefined);
  const projectId = $derived($auth.projectId ?? undefined);

  async function loadData() {
    loading = true;
    try {
      [fileStorages, libraries] = await Promise.all([
        api.get<FileStorage[]>('/api/admin/file-storage', token, projectId),
        api.get<LibraryConfig[]>('/api/libraries', token, projectId),
      ]);
    } catch (e) {
      error = e instanceof ApiError ? `로드 실패: ${e.message}` : '서버 오류';
    } finally {
      loading = false;
    }
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
    loading = true;
    untrack(() => loadData());
  });

  $effect(() => {
    if (!$auth.projectId || !autoRefresh) return;
    const interval = setInterval(() => untrack(() => loadData()), 10000);
    return () => clearInterval(interval);
  });
</script>

<div class="p-4 md:p-8 max-w-5xl">
  <div class="flex items-center justify-between mb-6">
    <div>
      <h1 class="text-2xl font-bold text-white">라이브러리 파일 스토리지 관리</h1>
      <p class="text-sm text-gray-500 mt-1">Strategy A (사전 빌드)에서 사용할 Manila CephFS 파일 스토리지를 관리합니다.</p>
    </div>
    <div class="flex items-center gap-3">
      <label class="flex items-center gap-2 text-xs text-gray-400 cursor-pointer">
        <input type="checkbox" bind:checked={autoInstall} class="rounded border-gray-600 bg-gray-800 text-blue-500 focus:ring-blue-500 focus:ring-offset-0" />
        자동 패키지 설치
      </label>
      <AutoRefreshToggle bind:active={autoRefresh} intervalSeconds={10} />
      <button onclick={loadData} class="text-xs text-gray-400 hover:text-white transition-colors border border-gray-700 hover:border-gray-500 px-3 py-1.5 rounded-lg">새로고침</button>
    </div>
  </div>

  {#if error}
    <div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>
  {/if}
  {#if message}
    <div class="bg-green-900/40 border border-green-700 text-green-300 rounded-lg px-4 py-3 text-sm mb-4">{message}</div>
  {/if}

  {#if loading}
    <LoadingSkeleton variant="list" rows={4} />
  {:else}
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
                <span class="text-xs {statusColor[prebuilt.status] ?? 'text-gray-400'}">{prebuilt.status}</span>
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
      <div class="text-gray-600 text-sm">파일 스토리지가 없습니다</div>
    {:else}
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
              <th class="text-left py-2 pr-4">이름</th>
              <th class="text-left py-2 pr-4">상태</th>
              <th class="text-left py-2 pr-4">크기</th>
              <th class="text-left py-2 pr-4">타입</th>
              <th class="text-left py-2">라이브러리</th>
            </tr>
          </thead>
          <tbody>
            {#each fileStorages as fs}
              <tr class="border-b border-gray-800/50 text-xs">
                <td class="py-2 pr-4 font-mono text-gray-300">{fs.name}</td>
                <td class="py-2 pr-4 {statusColor[fs.status] ?? 'text-gray-400'}">{fs.status}</td>
                <td class="py-2 pr-4 text-gray-400">{fs.size} GB</td>
                <td class="py-2 pr-4 text-gray-500">{fs.metadata?.union_type ?? '-'}</td>
                <td class="py-2 text-gray-500">{fs.library_name ?? '-'}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  {/if}
</div>
