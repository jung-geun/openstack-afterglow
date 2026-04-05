<script lang="ts">
  import { auth } from '$lib/stores/auth';
  import { api, ApiError, memoryCache } from '$lib/api/client';
  import type { Share } from '$lib/types/resources';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';

  const statusColor: Record<string, string> = {
    available: 'text-green-400 bg-green-900/30',
    creating:  'text-yellow-400 bg-yellow-900/30',
    deleting:  'text-orange-400 bg-orange-900/30',
    error:     'text-red-400 bg-red-900/30',
  };

  let shares = $state<Share[]>([]);
  let loading = $state(true);
  let error = $state('');
  let deleting = $state<string | null>(null);
  let showModal = $state(false);
  let creating = $state(false);
  let createError = $state('');
  let form = $state({ name: '', size_gb: 10 });

  function swrGet<T>(path: string): T | null {
    const key = `${path}:${$auth.projectId}`;
    const c = memoryCache.get(key);
    return c ? (c.data as T) : null;
  }
  function swrSet(path: string, data: unknown) {
    memoryCache.set(`${path}:${$auth.projectId}`, { data, timestamp: Date.now() });
  }

  async function fetchShares() {
    const path = '/api/shares';
    const cached = swrGet<Share[]>(path);
    if (cached && shares.length === 0) shares = cached;
    try {
      shares = await api.get<Share[]>(path, $auth.token ?? undefined, $auth.projectId ?? undefined);
      swrSet(path, shares);
      error = '';
    } catch (e) {
      if (!cached) error = e instanceof ApiError ? `조회 실패 (${e.status})` : '서버 오류';
    } finally {
      loading = false;
    }
  }

  async function createShare() {
    if (!form.name.trim() || form.size_gb < 1) return;
    creating = true;
    createError = '';
    try {
      await api.post('/api/shares', form, $auth.token ?? undefined, $auth.projectId ?? undefined);
      showModal = false;
      form = { name: '', size_gb: 10 };
      await fetchShares();
    } catch (e) {
      createError = e instanceof ApiError ? e.message : '생성 실패';
    } finally {
      creating = false;
    }
  }

  async function deleteShare(id: string, name: string) {
    if (!confirm(`공유 스토리지 "${name || id.slice(0, 8)}"을 삭제하시겠습니까?`)) return;
    deleting = id;
    try {
      await api.delete(`/api/shares/${id}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
      await fetchShares();
    } catch (e) {
      alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
    } finally {
      deleting = null;
    }
  }

  $effect(() => {
    const projectId = $auth.projectId;
    if (!projectId) return;
    loading = true;
    fetchShares();
    const interval = setInterval(fetchShares, 10000);
    return () => clearInterval(interval);
  });
</script>

{#if showModal}
  <div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onclick={() => { showModal = false; createError = ''; }} role="dialog" aria-modal="true" tabindex="-1" onkeydown={(e) => e.key === 'Escape' && (showModal = false)}>
    <div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()} role="document" onkeydown={(e) => e.stopPropagation()}>
      <h2 class="text-lg font-semibold text-white mb-5">공유 스토리지 생성</h2>
      <div class="space-y-4">
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름</label>
          <input bind:value={form.name} type="text" placeholder="my-share" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">크기 (GB)</label>
          <input bind:value={form.size_gb} type="number" min="1" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
        </div>
      </div>
      {#if createError}<div class="mt-4 text-red-400 text-xs bg-red-900/20 border border-red-800 rounded px-3 py-2">{createError}</div>{/if}
      <div class="flex justify-end gap-3 mt-6">
        <button onclick={() => { showModal = false; createError = ''; }} class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">취소</button>
        <button onclick={createShare} disabled={creating} class="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors">{creating ? '생성 중...' : '생성'}</button>
      </div>
    </div>
  </div>
{/if}

<div class="p-8">
  <div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold text-white">공유 스토리지</h1>
    <button onclick={() => showModal = true} class="bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">+ 공유 생성</button>
  </div>

  {#if error}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>{/if}

  {#if loading}
    <LoadingSkeleton variant="table" rows={5} />
  {:else if shares.length === 0}
    <div class="text-center py-20 text-gray-600">
      <div class="text-5xl mb-4">🗂️</div>
      <p class="text-lg">공유 스토리지가 없습니다</p>
      <button onclick={() => showModal = true} class="text-blue-400 hover:text-blue-300 text-sm mt-2 inline-block">첫 공유 스토리지를 생성하세요 →</button>
    </div>
  {:else}
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
            <th class="text-left py-3 pr-6">이름</th>
            <th class="text-left py-3 pr-6">상태</th>
            <th class="text-left py-3 pr-6">크기</th>
            <th class="text-left py-3 pr-6">프로토콜</th>
            <th class="text-left py-3 pr-6">라이브러리</th>
            <th class="text-right py-3">액션</th>
          </tr>
        </thead>
        <tbody>
          {#each shares as share (share.id)}
            <tr class="border-b border-gray-800/50 hover:bg-gray-800/50 transition-colors">
              <td class="py-3 pr-6 font-medium">
                {#if share.name}<span class="text-white">{share.name}</span>{:else}<span class="text-gray-400 font-mono text-xs">{share.id}</span>{/if}
              </td>
              <td class="py-3 pr-6"><span class="px-2 py-0.5 rounded text-xs font-medium {statusColor[share.status] ?? 'text-gray-400 bg-gray-800'}">{share.status}</span></td>
              <td class="py-3 pr-6 text-gray-400">{share.size} GB</td>
              <td class="py-3 pr-6 text-gray-400 text-xs">{share.share_proto}</td>
              <td class="py-3 pr-6 text-xs">
                {#if share.library_name}
                  <span class="px-1.5 py-0.5 bg-blue-900/40 text-blue-300 rounded text-xs">{share.library_name}{share.library_version ? ` v${share.library_version}` : ''}</span>
                {:else}
                  <span class="text-gray-600">-</span>
                {/if}
              </td>
              <td class="py-3 text-right">
                <button onclick={(e) => { e.stopPropagation(); deleteShare(share.id, share.name); }} disabled={deleting === share.id} class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-1 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors">
                  {deleting === share.id ? '삭제 중...' : '삭제'}
                </button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
