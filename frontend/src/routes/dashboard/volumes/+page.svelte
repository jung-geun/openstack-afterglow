<script lang="ts">
  import { auth } from '$lib/stores/auth';
  import { untrack } from 'svelte';
  import { api, ApiError, memoryCache } from '$lib/api/client';
  import type { Volume } from '$lib/types/resources';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
  import VolumeDetailPanel from '$lib/components/VolumeDetailPanel.svelte';
  import VolumeTransferModal from '$lib/components/VolumeTransferModal.svelte';
  import SlidePanel from '$lib/components/SlidePanel.svelte';
  import RefreshButton from '$lib/components/RefreshButton.svelte';
  import AutoRefreshToggle from '$lib/components/AutoRefreshToggle.svelte';
  import { formatStorage } from '$lib/utils/format';

  const statusColor: Record<string, string> = {
    available:          'text-green-400 bg-green-900/30',
    creating:           'text-amber-400 bg-amber-900/30',
    deleting:           'text-orange-400 bg-orange-900/30',
    error:              'text-red-400 bg-red-900/30',
    in_use:             'text-blue-400 bg-blue-900/30',
    reserved:           'text-purple-400 bg-purple-900/30',
    attaching:          'text-cyan-400 bg-cyan-900/30',
    detaching:          'text-amber-400 bg-amber-900/30',
    'backing-up':       'text-indigo-400 bg-indigo-900/30',
    'restoring-backup': 'text-teal-400 bg-teal-900/30',
    downloading:        'text-sky-400 bg-sky-900/30',
    uploading:          'text-sky-400 bg-sky-900/30',
    retyping:           'text-violet-400 bg-violet-900/30',
    extending:          'text-cyan-400 bg-cyan-900/30',
    error_deleting:     'text-rose-400 bg-rose-900/30',
    error_backing_up:   'text-rose-400 bg-rose-900/30',
    error_restoring:    'text-rose-400 bg-rose-900/30',
    error_extending:    'text-rose-400 bg-rose-900/30',
  };

  let volumes = $state<Volume[]>([]);
  let loading = $state(true);
  let refreshing = $state(false);
  let error = $state('');
  let deleting = $state<string | null>(null);
  let showModal = $state(false);
  let showTransferModal = $state(false);
  let transferVolumeId = $state('');
  let transferVolumeName = $state('');
  let creating = $state(false);
  let createError = $state('');
  let form = $state({ name: '', size_gb: 10 });
  let autoRefresh = $state(false);

  let selectedVolumeId = $state<string | null>(null);

  function openVolumePanel(id: string) {
    selectedVolumeId = id;
    history.pushState({ volumeId: id }, '', `/dashboard/volumes/${id}`);
  }

  function closeVolumePanel() {
    selectedVolumeId = null;
    history.pushState({}, '', '/dashboard/volumes');
  }

  function swrGet<T>(path: string): T | null {
    const key = `${path}:${$auth.projectId}`;
    const c = memoryCache.get(key);
    return c ? (c.data as T) : null;
  }
  function swrSet(path: string, data: unknown) {
    memoryCache.set(`${path}:${$auth.projectId}`, { data, timestamp: Date.now() });
  }

  async function fetchVolumes(manual = false) {
    const path = '/api/volumes';
    const cached = swrGet<Volume[]>(path);
    if (cached && volumes.length === 0) volumes = cached;
    if (manual) refreshing = true;
    try {
      volumes = await api.get<Volume[]>(path, $auth.token ?? undefined, $auth.projectId ?? undefined, manual ? { refresh: true } : undefined);
      swrSet(path, volumes);
      error = '';
    } catch (e) {
      if (!cached) error = e instanceof ApiError ? `조회 실패 (${e.status})` : '서버 오류';
    } finally {
      loading = false;
      refreshing = false;
    }
  }

  async function createVolume() {
    if (!form.name.trim() || form.size_gb < 1) return;
    creating = true;
    createError = '';
    try {
      await api.post('/api/volumes', form, $auth.token ?? undefined, $auth.projectId ?? undefined);
      showModal = false;
      form = { name: '', size_gb: 10 };
      await fetchVolumes();
    } catch (e) {
      createError = e instanceof ApiError ? e.message : '생성 실패';
    } finally {
      creating = false;
    }
  }

  async function deleteVolume(id: string, name: string) {
    if (!confirm(`볼륨 "${name || id.slice(0, 8)}"을 삭제하시겠습니까?`)) return;
    deleting = id;
    try {
      await api.delete(`/api/volumes/${id}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
      await fetchVolumes();
    } catch (e) {
      alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
    } finally {
      deleting = null;
    }
  }

  function openTransferModal(id: string, name: string) {
    transferVolumeId = id;
    transferVolumeName = name;
    showTransferModal = true;
  }

  async function forceDeleteVolume(id: string, name: string) {
    if (!confirm(`볼륨 "${name || id.slice(0, 8)}"을 강제 삭제하시겠습니까?\n이 작업은 오류 상태 볼륨을 강제로 제거합니다.`)) return;
    deleting = id;
    try {
      await api.post(`/api/volumes/${id}/force-delete`, {}, $auth.token ?? undefined, $auth.projectId ?? undefined);
      await fetchVolumes();
    } catch (e) {
      alert('강제 삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
    } finally {
      deleting = null;
    }
  }

  $effect(() => {
    const projectId = $auth.projectId;
    if (!projectId) return;
    loading = true;
    untrack(() => { fetchVolumes(); });
  });

  $effect(() => {
    if (!$auth.projectId || !autoRefresh) return;
    const interval = setInterval(() => untrack(() => { fetchVolumes(); }), 10000);
    return () => clearInterval(interval);
  });
</script>

<svelte:window onkeydown={(e) => e.key === 'Escape' && selectedVolumeId && closeVolumePanel()} />

{#if showModal}
  <div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onclick={() => { showModal = false; createError = ''; }} role="dialog" aria-modal="true" tabindex="-1" onkeydown={(e) => e.key === 'Escape' && (showModal = false)}>
    <div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()} role="none" onkeydown={(e) => e.stopPropagation()}>
      <h2 class="text-lg font-semibold text-white mb-5">볼륨 생성</h2>
      <div class="space-y-4">
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름
            <input bind:value={form.name} type="text" placeholder="my-volume" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
          </label>
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">크기 (GB)
            <input bind:value={form.size_gb} type="number" min="1" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
          </label>
        </div>
      </div>
      {#if createError}<div class="mt-4 text-red-400 text-xs bg-red-900/20 border border-red-800 rounded px-3 py-2">{createError}</div>{/if}
      <div class="flex justify-end gap-3 mt-6">
        <button onclick={() => { showModal = false; createError = ''; }} class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">취소</button>
        <button onclick={createVolume} disabled={creating} class="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors">{creating ? '생성 중...' : '생성'}</button>
      </div>
    </div>
  </div>
{/if}

<div class="p-4 md:p-8">
  <div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold text-white">볼륨</h1>
    <div class="flex items-center gap-2">
      <AutoRefreshToggle bind:active={autoRefresh} intervalSeconds={10} />
      <RefreshButton {refreshing} onclick={() => fetchVolumes(true)} />
      <button onclick={() => showModal = true} class="bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">+ 볼륨 생성</button>
    </div>
  </div>

  {#if error}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>{/if}

  {#if loading}
    <LoadingSkeleton variant="table" rows={5} />
  {:else if volumes.length === 0}
    <div class="text-center py-20 text-gray-600">
      <div class="text-5xl mb-4">💾</div>
      <p class="text-lg">볼륨이 없습니다</p>
      <button onclick={() => showModal = true} class="text-blue-400 hover:text-blue-300 text-sm mt-2 inline-block">첫 볼륨을 생성하세요 →</button>
    </div>
  {:else}
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
            <th class="text-left py-3 pr-6">이름</th>
            <th class="text-left py-3 pr-6">상태</th>
            <th class="text-left py-3 pr-6">크기</th>
            <th class="text-left py-3 pr-6">타입</th>
            <th class="text-left py-3 pr-6">연결된 인스턴스</th>
            <th class="text-right py-3">액션</th>
          </tr>
        </thead>
        <tbody>
          {#each volumes as vol (vol.id)}
            <tr
              onclick={() => openVolumePanel(vol.id)}
              onkeydown={(e) => e.key === 'Enter' && openVolumePanel(vol.id)}
              tabindex="0"
              role="button"
              class="border-b border-gray-800/50 hover:bg-gray-800/50 transition-colors cursor-pointer {selectedVolumeId === vol.id ? 'bg-gray-800/30' : ''}"
            >
              <td class="py-3 pr-6 font-medium">
                {#if vol.name}<span class="text-white">{vol.name}</span>{:else}<span class="text-gray-400 font-mono text-xs">{vol.id}</span>{/if}
              </td>
              <td class="py-3 pr-6"><span class="px-2 py-0.5 rounded text-xs font-medium {statusColor[vol.status] ?? 'text-gray-400 bg-gray-800'}">{vol.status}</span></td>
              <td class="py-3 pr-6 text-gray-400">{formatStorage(vol.size)}</td>
              <td class="py-3 pr-6 text-gray-400 text-xs">{vol.volume_type ?? '-'}</td>
              <td class="py-3 pr-6 text-xs">
                {#if vol.attachments.length > 0}
                  <span class="text-blue-400">{vol.attachments.length}개 연결</span>
                {:else}
                  <span class="text-gray-500">미연결</span>
                {/if}
              </td>
              <td class="py-3 text-right">
                <div class="flex items-center justify-end gap-1">
                  {#if vol.status === 'available'}
                    <button
                      onclick={(e) => { e.stopPropagation(); openVolumePanel(vol.id); }}
                      class="text-blue-400 hover:text-blue-300 text-xs px-2 py-1 rounded border border-blue-900 hover:border-blue-700 transition-colors"
                    >연결</button>
                    <button
                      onclick={(e) => { e.stopPropagation(); openTransferModal(vol.id, vol.name); }}
                      class="text-violet-400 hover:text-violet-300 text-xs px-2 py-1 rounded border border-violet-900 hover:border-violet-700 transition-colors"
                      title="다른 프로젝트로 볼륨 이전"
                    >이전</button>
                  {/if}
                  {#if (vol.status === 'error' || vol.status === 'error_deleting' || vol.status === 'deleting') && $auth.isSystemAdmin}
                    <button
                      onclick={(e) => { e.stopPropagation(); forceDeleteVolume(vol.id, vol.name); }}
                      disabled={deleting === vol.id}
                      class="text-rose-400 hover:text-rose-300 disabled:text-gray-600 text-xs px-2 py-1 rounded border border-rose-900 hover:border-rose-700 disabled:border-gray-700 transition-colors"
                      title="오류 상태 볼륨 강제 삭제 (관리자)"
                    >{deleting === vol.id ? '삭제 중...' : '강제 삭제'}</button>
                  {/if}
                  <button
                    onclick={(e) => { e.stopPropagation(); deleteVolume(vol.id, vol.name); }}
                    disabled={deleting === vol.id || vol.attachments.length > 0}
                    class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-1 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors"
                    title={vol.attachments.length > 0 ? '연결된 볼륨은 삭제할 수 없습니다' : ''}
                  >{deleting === vol.id ? '삭제 중...' : '삭제'}</button>
                </div>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<!-- Volume Detail Panel -->
{#if selectedVolumeId}
  <SlidePanel onClose={closeVolumePanel} width="w-full md:w-[60vw] max-w-2xl">
    <VolumeDetailPanel
      volumeId={selectedVolumeId}
      onClose={closeVolumePanel}
      onDeleted={() => { fetchVolumes(); closeVolumePanel(); }}
    />
  </SlidePanel>
{/if}

<!-- Volume Transfer Modal -->
{#if showTransferModal}
  <VolumeTransferModal
    volumeId={transferVolumeId}
    volumeName={transferVolumeName}
    onClose={() => showTransferModal = false}
    onTransferred={() => { fetchVolumes(); showTransferModal = false; }}
  />
{/if}
