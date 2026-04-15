<script lang="ts">
  import { auth } from '$lib/stores/auth';
  import { untrack } from 'svelte';
  import { api, ApiError } from '$lib/api/client';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
  import { formatStorage } from '$lib/utils/format';
  import RefreshButton from '$lib/components/RefreshButton.svelte';
  import AutoRefreshToggle from '$lib/components/AutoRefreshToggle.svelte';

  interface VolumeSnapshot {
    id: string;
    name: string;
    status: string;
    volume_id: string;
    size: number;
    description: string;
    created_at: string | null;
  }

  interface Volume {
    id: string;
    name: string;
    size: number;
  }

  const statusColor: Record<string, string> = {
    available:        'text-green-400 bg-green-900/30',
    creating:         'text-amber-400 bg-amber-900/30',
    deleting:         'text-orange-400 bg-orange-900/30',
    error:            'text-red-400 bg-red-900/30',
    error_deleting:   'text-rose-400 bg-rose-900/30',
  };

  let snapshots = $state<VolumeSnapshot[]>([]);
  let volumes = $state<Volume[]>([]);
  let loading = $state(true);
  let refreshing = $state(false);
  let error = $state('');
  let autoRefresh = $state(false);
  let deleting = $state<string | null>(null);
  let showModal = $state(false);
  let creating = $state(false);
  let createError = $state('');
  let form = $state({ volume_id: '', name: '', description: '', force: false });

  async function fetchSnapshots() {
    try {
      snapshots = await api.get<VolumeSnapshot[]>('/api/volume-snapshots', $auth.token ?? undefined, $auth.projectId ?? undefined);
      error = '';
    } catch (e) {
      error = e instanceof ApiError ? `조회 실패 (${e.status})` : '서버 오류';
    } finally {
      loading = false;
    }
  }

  async function fetchVolumes() {
    try {
      volumes = await api.get<Volume[]>('/api/volumes', $auth.token ?? undefined, $auth.projectId ?? undefined);
    } catch { /* ignore */ }
  }

  async function createSnapshot() {
    if (!form.volume_id || !form.name.trim()) return;
    creating = true;
    createError = '';
    try {
      await api.post('/api/volume-snapshots', form, $auth.token ?? undefined, $auth.projectId ?? undefined);
      showModal = false;
      form = { volume_id: '', name: '', description: '', force: false };
      await fetchSnapshots();
    } catch (e) {
      createError = e instanceof ApiError ? e.message : '생성 실패';
    } finally {
      creating = false;
    }
  }

  async function deleteSnapshot(id: string, name: string) {
    if (!confirm(`스냅샷 "${name || id.slice(0, 8)}"을 삭제하시겠습니까?`)) return;
    deleting = id;
    try {
      await api.delete(`/api/volume-snapshots/${id}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
      await fetchSnapshots();
    } catch (e) {
      alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
    } finally {
      deleting = null;
    }
  }

  async function forceRefresh() {
    refreshing = true;
    try {
      await fetchSnapshots();
    } finally {
      refreshing = false;
    }
  }

  $effect(() => {
    const pid = $auth.projectId;
    if (!pid) return;
    untrack(() => { fetchSnapshots(); fetchVolumes(); });
  });

  $effect(() => {
    if (!$auth.projectId || !autoRefresh) return;
    const interval = setInterval(() => untrack(() => { fetchSnapshots(); }), 15000);
    return () => clearInterval(interval);
  });
</script>

{#if showModal}
  <div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onclick={() => { showModal = false; createError = ''; }} role="dialog" aria-modal="true" tabindex="-1" onkeydown={(e) => e.key === 'Escape' && (showModal = false)}>
    <div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()} role="none" onkeydown={(e) => e.stopPropagation()}>
      <h2 class="text-lg font-semibold text-white mb-5">볼륨 스냅샷 생성</h2>
      <div class="space-y-4">
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">볼륨 선택
            <select bind:value={form.volume_id} class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5">
              <option value="">볼륨을 선택하세요</option>
              {#each volumes as vol}
                <option value={vol.id}>{vol.name || vol.id.slice(0, 8)} ({formatStorage(vol.size)})</option>
              {/each}
            </select>
          </label>
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">스냅샷 이름
            <input bind:value={form.name} type="text" placeholder="my-snapshot" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
          </label>
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">설명 (선택)
            <input bind:value={form.description} type="text" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
          </label>
        </div>
        <div class="flex items-center gap-2">
          <input type="checkbox" id="force" bind:checked={form.force} class="rounded border-gray-600" />
          <label for="force" class="text-sm text-gray-300">연결된 볼륨 강제 스냅샷 (force)</label>
        </div>
      </div>
      {#if createError}<div class="mt-4 text-red-400 text-xs">{createError}</div>{/if}
      <div class="flex justify-end gap-3 mt-6">
        <button onclick={() => { showModal = false; createError = ''; }} class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">취소</button>
        <button onclick={createSnapshot} disabled={creating} class="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors">{creating ? '생성 중...' : '생성'}</button>
      </div>
    </div>
  </div>
{/if}

<div class="p-4 md:p-8">
  <div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold text-white">볼륨 스냅샷</h1>
    <div class="flex items-center gap-2">
      <AutoRefreshToggle bind:active={autoRefresh} intervalSeconds={15} />
      <RefreshButton {refreshing} onclick={forceRefresh} />
      <button onclick={() => showModal = true} class="bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">+ 스냅샷 생성</button>
    </div>
  </div>

  {#if error}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>{/if}

  {#if loading}
    <LoadingSkeleton variant="table" rows={4} />
  {:else if snapshots.length === 0}
    <div class="text-center py-20 text-gray-600">
      <div class="text-5xl mb-4">📸</div>
      <p class="text-lg">볼륨 스냅샷이 없습니다</p>
      <button onclick={() => showModal = true} class="text-blue-400 hover:text-blue-300 text-sm mt-2 inline-block">첫 스냅샷을 생성하세요 →</button>
    </div>
  {:else}
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
            <th class="text-left py-3 pr-6">이름</th>
            <th class="text-left py-3 pr-6">상태</th>
            <th class="text-left py-3 pr-6">크기</th>
            <th class="text-left py-3 pr-6">볼륨 ID</th>
            <th class="text-left py-3 pr-6">설명</th>
            <th class="text-left py-3 pr-6">생성일</th>
            <th class="text-right py-3">액션</th>
          </tr>
        </thead>
        <tbody>
          {#each snapshots as snap (snap.id)}
            <tr class="border-b border-gray-800/50 hover:bg-gray-800/50 transition-colors">
              <td class="py-3 pr-6 font-medium text-white">{snap.name || snap.id.slice(0, 8)}</td>
              <td class="py-3 pr-6"><span class="px-2 py-0.5 rounded text-xs font-medium {statusColor[snap.status] ?? 'text-gray-400 bg-gray-800'}">{snap.status}</span></td>
              <td class="py-3 pr-6 text-gray-400">{formatStorage(snap.size)}</td>
              <td class="py-3 pr-6 text-gray-500 font-mono text-xs">{snap.volume_id.slice(0, 8)}…</td>
              <td class="py-3 pr-6 text-gray-400 text-xs">{snap.description || '-'}</td>
              <td class="py-3 pr-6 text-gray-400 text-xs">{snap.created_at ? new Date(snap.created_at).toLocaleDateString('ko-KR') : '-'}</td>
              <td class="py-3 text-right">
                <button
                  onclick={() => deleteSnapshot(snap.id, snap.name)}
                  disabled={deleting === snap.id}
                  class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-1 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors"
                >
                  {deleting === snap.id ? '삭제 중...' : '삭제'}
                </button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
