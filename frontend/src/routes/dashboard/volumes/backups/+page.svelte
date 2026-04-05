<script lang="ts">
  import { onMount } from 'svelte';
  import { auth } from '$lib/stores/auth';
  import { api, ApiError } from '$lib/api/client';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';

  interface VolumeBackup {
    id: string;
    name: string;
    status: string;
    volume_id: string;
    size: number;
    is_incremental: boolean;
    description: string;
    created_at: string | null;
  }

  interface Volume {
    id: string;
    name: string;
    size: number;
  }

  let backups = $state<VolumeBackup[]>([]);
  let volumes = $state<Volume[]>([]);
  let loading = $state(true);
  let error = $state('');
  let deleting = $state<string | null>(null);
  let showModal = $state(false);
  let creating = $state(false);
  let createError = $state('');
  let form = $state({ volume_id: '', name: '', description: '', incremental: false });

  const statusColor: Record<string, string> = {
    available: 'text-green-400 bg-green-900/30',
    creating:  'text-yellow-400 bg-yellow-900/30',
    deleting:  'text-orange-400 bg-orange-900/30',
    error:     'text-red-400 bg-red-900/30',
  };

  async function fetchBackups() {
    try {
      backups = await api.get<VolumeBackup[]>('/api/volumes/backups', $auth.token ?? undefined, $auth.projectId ?? undefined);
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

  async function createBackup() {
    if (!form.volume_id || !form.name.trim()) return;
    creating = true;
    createError = '';
    try {
      await api.post('/api/volumes/backups', form, $auth.token ?? undefined, $auth.projectId ?? undefined);
      showModal = false;
      form = { volume_id: '', name: '', description: '', incremental: false };
      await fetchBackups();
    } catch (e) {
      createError = e instanceof ApiError ? e.message : '생성 실패';
    } finally {
      creating = false;
    }
  }

  async function deleteBackup(id: string, name: string) {
    if (!confirm(`백업 "${name || id.slice(0, 8)}"을 삭제하시겠습니까?`)) return;
    deleting = id;
    try {
      await api.delete(`/api/volumes/backups/${id}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
      await fetchBackups();
    } catch (e) {
      alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
    } finally {
      deleting = null;
    }
  }

  onMount(() => { fetchBackups(); fetchVolumes(); });
</script>

{#if showModal}
  <div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onclick={() => { showModal = false; createError = ''; }} role="dialog" aria-modal="true" tabindex="-1" onkeydown={(e) => e.key === 'Escape' && (showModal = false)}>
    <div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()} role="document" onkeydown={(e) => e.stopPropagation()}>
      <h2 class="text-lg font-semibold text-white mb-5">볼륨 백업 생성</h2>
      <div class="space-y-4">
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">볼륨 선택</label>
          <select bind:value={form.volume_id} class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500">
            <option value="">볼륨을 선택하세요</option>
            {#each volumes as vol}
              <option value={vol.id}>{vol.name || vol.id.slice(0, 8)} ({vol.size} GB)</option>
            {/each}
          </select>
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">백업 이름</label>
          <input bind:value={form.name} type="text" placeholder="my-backup" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">설명 (선택)</label>
          <input bind:value={form.description} type="text" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
        </div>
        <div class="flex items-center gap-2">
          <input type="checkbox" id="incremental" bind:checked={form.incremental} class="rounded border-gray-600" />
          <label for="incremental" class="text-sm text-gray-300">증분 백업</label>
        </div>
      </div>
      {#if createError}<div class="mt-4 text-red-400 text-xs">{createError}</div>{/if}
      <div class="flex justify-end gap-3 mt-6">
        <button onclick={() => { showModal = false; createError = ''; }} class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">취소</button>
        <button onclick={createBackup} disabled={creating} class="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors">{creating ? '생성 중...' : '생성'}</button>
      </div>
    </div>
  </div>
{/if}

<div class="p-8">
  <div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold text-white">볼륨 백업</h1>
    <button onclick={() => showModal = true} class="bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">+ 백업 생성</button>
  </div>

  {#if error}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>{/if}

  {#if loading}
    <LoadingSkeleton variant="table" rows={4} />
  {:else if backups.length === 0}
    <div class="text-center py-20 text-gray-600">
      <div class="text-5xl mb-4">📦</div>
      <p class="text-lg">볼륨 백업이 없습니다</p>
    </div>
  {:else}
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
            <th class="text-left py-3 pr-6">이름</th>
            <th class="text-left py-3 pr-6">상태</th>
            <th class="text-left py-3 pr-6">크기</th>
            <th class="text-left py-3 pr-6">증분</th>
            <th class="text-left py-3 pr-6">생성일</th>
            <th class="text-right py-3">액션</th>
          </tr>
        </thead>
        <tbody>
          {#each backups as backup (backup.id)}
            <tr class="border-b border-gray-800/50 hover:bg-gray-800/50 transition-colors">
              <td class="py-3 pr-6 font-medium text-white">{backup.name || backup.id.slice(0, 8)}</td>
              <td class="py-3 pr-6"><span class="px-2 py-0.5 rounded text-xs font-medium {statusColor[backup.status] ?? 'text-gray-400 bg-gray-800'}">{backup.status}</span></td>
              <td class="py-3 pr-6 text-gray-400">{backup.size} GB</td>
              <td class="py-3 pr-6"><span class="text-xs {backup.is_incremental ? 'text-blue-400' : 'text-gray-500'}">{backup.is_incremental ? '증분' : '전체'}</span></td>
              <td class="py-3 pr-6 text-gray-400 text-xs">{backup.created_at ? new Date(backup.created_at).toLocaleDateString('ko-KR') : '-'}</td>
              <td class="py-3 text-right">
                <button onclick={() => deleteBackup(backup.id, backup.name)} disabled={deleting === backup.id} class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-1 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors">
                  {deleting === backup.id ? '삭제 중...' : '삭제'}
                </button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
