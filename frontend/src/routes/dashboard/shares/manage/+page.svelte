<script lang="ts">
  import { onMount } from 'svelte';
  import { auth } from '$lib/stores/auth';
  import { api, ApiError } from '$lib/api/client';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';

  interface Share {
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

  let shares = $state<Share[]>([]);
  let libraries = $state<LibraryConfig[]>([]);
  let building = $state<string | null>(null);
  let loading = $state(true);
  let error = $state('');
  let message = $state('');

  const token = $derived($auth.token ?? undefined);
  const projectId = $derived($auth.projectId ?? undefined);

  async function loadData() {
    loading = true;
    try {
      [shares, libraries] = await Promise.all([
        api.get<Share[]>('/api/admin/shares', token, projectId),
        api.get<LibraryConfig[]>('/api/libraries', token, projectId),
      ]);
    } catch (e) {
      error = e instanceof ApiError ? `로드 실패: ${e.message}` : '서버 오류';
    } finally {
      loading = false;
    }
  }

  async function buildShare(libId: string) {
    building = libId;
    message = '';
    error = '';
    try {
      const res = await api.post<{ share_id: string }>(
        `/api/admin/shares/build?library_id=${libId}`, {}, token, projectId
      );
      message = `Share 생성 시작됨 (ID: ${res.share_id})`;
      await loadData();
    } catch (e) {
      error = e instanceof ApiError ? `빌드 실패: ${e.message}` : '서버 오류';
    } finally {
      building = null;
    }
  }

  onMount(loadData);
</script>

<div class="p-8 max-w-5xl">
  <div class="flex items-center justify-between mb-6">
    <div>
      <h1 class="text-2xl font-bold text-white">라이브러리 Share 관리</h1>
      <p class="text-sm text-gray-500 mt-1">Strategy A (사전 빌드)에서 사용할 Manila CephFS share를 관리합니다.</p>
    </div>
    <button onclick={loadData} class="text-xs text-gray-400 hover:text-white transition-colors border border-gray-700 hover:border-gray-500 px-3 py-1.5 rounded-lg">새로고침</button>
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
          {@const prebuilt = shares.find(s => s.library_name === lib.id && s.metadata?.union_type === 'prebuilt')}
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
                Share ID: <span class="font-mono">{prebuilt.id.slice(0, 8)}...</span>
                {#if prebuilt.built_at}• {prebuilt.built_at.split('T')[0]}{/if}
              </div>
            {/if}
            <button
              onclick={() => buildShare(lib.id)}
              disabled={building === lib.id || !!prebuilt}
              class="w-full text-xs py-1.5 rounded-lg border transition-colors {prebuilt ? 'border-gray-700 text-gray-600 cursor-not-allowed' : 'border-blue-700 text-blue-400 hover:bg-blue-900/20'}"
            >
              {building === lib.id ? '생성 중...' : prebuilt ? '구축됨' : 'Share 생성'}
            </button>
          </div>
        {/each}
        {#if libraries.length === 0}
          <div class="col-span-2 text-gray-600 text-sm">라이브러리 정보를 불러올 수 없습니다</div>
        {/if}
      </div>
    </div>

    <div class="flex items-center justify-between mb-3">
      <h2 class="text-base font-semibold text-white">전체 Share 목록</h2>
    </div>
    {#if shares.length === 0}
      <div class="text-gray-600 text-sm">Share가 없습니다</div>
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
            {#each shares as share}
              <tr class="border-b border-gray-800/50 text-xs">
                <td class="py-2 pr-4 font-mono text-gray-300">{share.name}</td>
                <td class="py-2 pr-4 {statusColor[share.status] ?? 'text-gray-400'}">{share.status}</td>
                <td class="py-2 pr-4 text-gray-400">{share.size} GB</td>
                <td class="py-2 pr-4 text-gray-500">{share.metadata?.union_type ?? '-'}</td>
                <td class="py-2 text-gray-500">{share.library_name ?? '-'}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  {/if}
</div>
