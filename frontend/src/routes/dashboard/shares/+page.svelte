<script lang="ts">
  import { auth } from '$lib/stores/auth';
  import { untrack } from 'svelte';
  import { goto } from '$app/navigation';
  import { api, ApiError, memoryCache } from '$lib/api/client';
  import type { Share } from '$lib/types/resources';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';

  const statusColor: Record<string, string> = {
    available: 'text-green-400 bg-green-900/30',
    creating:  'text-yellow-400 bg-yellow-900/30',
    deleting:  'text-orange-400 bg-orange-900/30',
    error:     'text-red-400 bg-red-900/30',
  };

  interface QuotaItem { limit: number; in_use: number; }
  interface Quota {
    shares: QuotaItem;
    gigabytes: QuotaItem;
    share_networks: QuotaItem;
  }

  interface MetaEntry { key: string; value: string; }

  let shares = $state<Share[]>([]);
  let quota = $state<Quota | null>(null);
  let loading = $state(true);
  let error = $state('');
  let deleting = $state<string | null>(null);
  let showModal = $state(false);
  let creating = $state(false);
  let createError = $state('');
  let form = $state({ name: '', size_gb: 10, share_type: '', share_network_id: '', share_proto: 'CEPHFS' });
  let shareTypes = $state<{ id: string; name: string; is_default: boolean }[]>([]);
  let metaEntries = $state<MetaEntry[]>([{ key: '', value: '' }]);
  let copiedExport = $state<string | null>(null);

  function addMeta() { metaEntries = [...metaEntries, { key: '', value: '' }]; }
  function removeMeta(i: number) { metaEntries = metaEntries.filter((_, idx) => idx !== i); }

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

  async function fetchQuota() {
    try {
      quota = await api.get<Quota>('/api/shares/quota', $auth.token ?? undefined, $auth.projectId ?? undefined);
    } catch {
      quota = null;
    }
  }

  async function copyExportPath(path: string, shareId: string) {
    await navigator.clipboard.writeText(path);
    copiedExport = shareId;
    setTimeout(() => (copiedExport = null), 2000);
  }

  async function openCreateModal() {
    showModal = true;
    try {
      shareTypes = await api.get<{ id: string; name: string; is_default: boolean }[]>(
        '/api/shares/types', $auth.token ?? undefined, $auth.projectId ?? undefined
      );
      if (shareTypes.length > 0 && !form.share_type) {
        form.share_type = shareTypes.find(t => t.is_default)?.name ?? shareTypes[0].name;
      }
    } catch {
      shareTypes = [];
    }
  }

  async function createShare() {
    if (!form.name.trim() || form.size_gb < 1) return;
    creating = true;
    createError = '';
    try {
      const body: Record<string, unknown> = {
        name: form.name,
        size_gb: form.size_gb,
        share_type: form.share_type,
        share_proto: form.share_proto,
      };
      if (form.share_network_id.trim()) body.share_network_id = form.share_network_id.trim();
      const validMeta = metaEntries.filter(m => m.key.trim());
      if (validMeta.length > 0) {
        const metadata: Record<string, string> = {};
        validMeta.forEach(m => { metadata[m.key.trim()] = m.value; });
        body.metadata = metadata;
      }
      await api.post('/api/shares', body, $auth.token ?? undefined, $auth.projectId ?? undefined);
      showModal = false;
      form = { name: '', size_gb: 10, share_type: shareTypes[0]?.name ?? '', share_network_id: '', share_proto: 'CEPHFS' };
      metaEntries = [{ key: '', value: '' }];
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
    untrack(() => { fetchShares(); fetchQuota(); });
    const interval = setInterval(() => untrack(() => { fetchShares(); }), 10000);
    return () => clearInterval(interval);
  });
</script>

{#if showModal}
  <div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onclick={() => { showModal = false; createError = ''; }} role="dialog" aria-modal="true" tabindex="-1" onkeydown={(e) => e.key === 'Escape' && (showModal = false)}>
    <div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-lg mx-4 shadow-2xl max-h-[90vh] overflow-y-auto" onclick={(e) => e.stopPropagation()} role="none" onkeydown={(e) => e.stopPropagation()}>
      <h2 class="text-lg font-semibold text-white mb-5">공유 스토리지 생성</h2>
      <div class="space-y-4">
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름
            <input bind:value={form.name} type="text" placeholder="my-share" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
          </label>
        </div>
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">크기 (GB)
              <input bind:value={form.size_gb} type="number" min="1" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
            </label>
          </div>
          <div>
            <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">Share Type
              {#if shareTypes.length > 0}
                <select bind:value={form.share_type} class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5">
                  {#each shareTypes as st}
                    <option value={st.name}>{st.name}{st.is_default ? ' (기본값)' : ''}</option>
                  {/each}
                </select>
              {:else}
                <input bind:value={form.share_type} type="text" placeholder="share type 이름" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 font-mono mt-1.5" />
              {/if}
            </label>
          </div>
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">프로토콜
            <select bind:value={form.share_proto} class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5">
              <option value="CEPHFS">CephFS</option>
              <option value="NFS">NFS</option>
            </select>
          </label>
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">Share Network ID (선택)
            <input bind:value={form.share_network_id} type="text" placeholder="UUID (비워두면 기본값 사용)" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 font-mono mt-1.5" />
          </label>
        </div>
        <!-- 메타데이터 -->
        <div>
          <div class="flex items-center justify-between mb-2">
            <span class="block text-xs text-gray-400 uppercase tracking-wide">메타데이터 (선택)</span>
            <button type="button" onclick={addMeta} class="text-xs text-blue-400 hover:text-blue-300 transition-colors">+ 추가</button>
          </div>
          <div class="space-y-2">
            {#each metaEntries as meta, i (i)}
              <div class="flex gap-2 items-center">
                <input bind:value={meta.key} type="text" placeholder="key" class="flex-1 bg-gray-800 border border-gray-600 rounded-lg px-3 py-1.5 text-white text-xs focus:outline-none focus:border-blue-500 font-mono" />
                <span class="text-gray-600 text-xs">=</span>
                <input bind:value={meta.value} type="text" placeholder="value" class="flex-1 bg-gray-800 border border-gray-600 rounded-lg px-3 py-1.5 text-white text-xs focus:outline-none focus:border-blue-500 font-mono" />
                <button type="button" onclick={() => removeMeta(i)} class="text-gray-600 hover:text-red-400 transition-colors text-xs px-1">✕</button>
              </div>
            {/each}
          </div>
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

<div class="p-4 md:p-8">
  <div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold text-white">공유 스토리지</h1>
    <button onclick={openCreateModal} class="bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">+ 공유 생성</button>
  </div>

  <!-- 쿼터 표시 -->
  {#if quota}
    <div class="flex items-center gap-6 mb-6 bg-gray-900 border border-gray-800 rounded-lg px-5 py-3">
      <span class="text-xs text-gray-500 uppercase tracking-wide">쿼터</span>
      {#each [
        { label: 'Shares', item: quota.shares },
        { label: '용량', item: quota.gigabytes, unit: 'GB' },
        { label: 'Share Networks', item: quota.share_networks },
      ] as q}
        <div class="flex items-center gap-1.5">
          <span class="text-xs text-gray-400">{q.label}:</span>
          <span class="text-xs font-medium {q.item.limit > 0 && q.item.in_use / q.item.limit > 0.8 ? 'text-orange-400' : 'text-white'}">
            {q.item.in_use}{q.unit ?? ''}
          </span>
          {#if q.item.limit > 0}
            <span class="text-xs text-gray-600">/ {q.item.limit}{q.unit ?? ''}</span>
          {/if}
        </div>
      {/each}
    </div>
  {/if}

  {#if error}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>{/if}

  {#if loading}
    <LoadingSkeleton variant="table" rows={5} />
  {:else if shares.length === 0}
    <div class="text-center py-20 text-gray-600">
      <div class="text-5xl mb-4">🗂️</div>
      <p class="text-lg">공유 스토리지가 없습니다</p>
      <button onclick={openCreateModal} class="text-blue-400 hover:text-blue-300 text-sm mt-2 inline-block">첫 공유 스토리지를 생성하세요 →</button>
    </div>
  {:else}
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
            <th class="text-left py-3 pr-6">이름</th>
            <th class="text-left py-3 pr-6">상태</th>
            <th class="text-left py-3 pr-4">크기</th>
            <th class="text-left py-3 pr-4">프로토콜</th>
            <th class="text-left py-3 pr-6">라이브러리</th>
            <th class="text-left py-3 pr-6">Export Location</th>
            <th class="text-right py-3">액션</th>
          </tr>
        </thead>
        <tbody>
          {#each shares as share (share.id)}
            <tr class="border-b border-gray-800/50 hover:bg-gray-800/50 transition-colors">
              <td class="py-3 pr-6 font-medium">
                <button onclick={() => goto(`/dashboard/shares/${share.id}`)} class="text-white hover:text-blue-400 transition-colors text-left">
                  {#if share.name}<span>{share.name}</span>{:else}<span class="text-gray-400 font-mono text-xs">{share.id}</span>{/if}
                </button>
              </td>
              <td class="py-3 pr-6"><span class="px-2 py-0.5 rounded text-xs font-medium {statusColor[share.status] ?? 'text-gray-400 bg-gray-800'}">{share.status}</span></td>
              <td class="py-3 pr-4 text-gray-400 text-xs">{share.size} GB</td>
              <td class="py-3 pr-4 text-gray-400 text-xs">{share.share_proto}</td>
              <td class="py-3 pr-6 text-xs">
                {#if share.library_name}
                  <span class="px-1.5 py-0.5 bg-blue-900/40 text-blue-300 rounded text-xs">{share.library_name}{share.library_version ? ` v${share.library_version}` : ''}</span>
                {:else}
                  <span class="text-gray-600">-</span>
                {/if}
              </td>
              <td class="py-3 pr-6 text-xs max-w-[200px]">
                {#if share.export_locations && share.export_locations.length > 0}
                  <div class="flex items-center gap-1.5">
                    <span class="text-gray-500 font-mono truncate">{share.export_locations[0].slice(-32)}</span>
                    <button
                      onclick={(e) => { e.stopPropagation(); copyExportPath(share.export_locations[0], share.id); }}
                      class="shrink-0 text-gray-600 hover:text-gray-400 transition-colors"
                      title="경로 복사"
                    >
                      {copiedExport === share.id ? '✓' : '⎘'}
                    </button>
                  </div>
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
