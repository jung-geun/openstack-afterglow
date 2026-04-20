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
  import StatusChip from '$lib/components/ui/StatusChip.svelte';
  import PageHeader from '$lib/components/ui/PageHeader.svelte';

  interface Snapshot {
    id: string;
    name: string;
    status: string;
    volume_id: string;
    size: number;
    description: string;
    created_at: string | null;
  }

  let volumes = $state<Volume[]>([]);
  let snapshots = $state<Snapshot[]>([]);
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
  let tab = $state('volumes');

  let selectedVolumeId = $state<string | null>(null);
  let autoBackupConfigs = $state<Set<string>>(new Set());
  let autoBackupToggling = $state<string | null>(null);

  // Derived stats
  let totalGb = $derived(volumes.reduce((s, v) => s + v.size, 0));
  let attachedCount = $derived(volumes.filter(v => v.attachments.length > 0).length);
  let attachedGb = $derived(volumes.filter(v => v.attachments.length > 0).reduce((s, v) => s + v.size, 0));

  // Recent 24h snapshots
  let recentSnapshots = $derived(snapshots.filter(s => {
    if (!s.created_at) return false;
    return Date.now() - new Date(s.created_at).getTime() < 86400000;
  }));

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

  async function fetchSnapshots() {
    try {
      snapshots = await api.get<Snapshot[]>('/api/volume-snapshots', $auth.token ?? undefined, $auth.projectId ?? undefined);
    } catch { /* 오류 무시 */ }
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

  async function fetchAutoBackupConfigs() {
    try {
      const configs = await api.post<{ volume_id: string }[]>(
        '/api/volumes/backups/auto-backup/configs', {},
        $auth.token ?? undefined, $auth.projectId ?? undefined
      );
      autoBackupConfigs = new Set(configs.map(c => c.volume_id));
    } catch { /* 오류 무시 */ }
  }

  async function toggleAutoBackup(volumeId: string) {
    autoBackupToggling = volumeId;
    try {
      if (autoBackupConfigs.has(volumeId)) {
        await api.delete(`/api/volumes/backups/auto-backup/${volumeId}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
        autoBackupConfigs = new Set([...autoBackupConfigs].filter(id => id !== volumeId));
      } else {
        await api.post(`/api/volumes/backups/auto-backup/${volumeId}`, {}, $auth.token ?? undefined, $auth.projectId ?? undefined);
        autoBackupConfigs = new Set([...autoBackupConfigs, volumeId]);
      }
    } catch (e) {
      alert('자동 백업 설정 실패: ' + (e instanceof ApiError ? e.message : String(e)));
    } finally {
      autoBackupToggling = null;
    }
  }

  $effect(() => {
    const projectId = $auth.projectId;
    if (!projectId) return;
    loading = true;
    untrack(() => { fetchVolumes(); fetchAutoBackupConfigs(); fetchSnapshots(); });
  });

  $effect(() => {
    if (!$auth.projectId || !autoRefresh) return;
    const interval = setInterval(() => untrack(() => { fetchVolumes(); fetchSnapshots(); }), 10000);
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
  <PageHeader breadcrumb="VOLUMES / BLOCK VOLUMES" title="블록 볼륨">
    {#snippet actions()}
      <AutoRefreshToggle bind:active={autoRefresh} intervalSeconds={10} />
      <RefreshButton {refreshing} onclick={() => fetchVolumes(true)} />
      <button onclick={() => showModal = true} class="bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">+ 볼륨 생성</button>
    {/snippet}
  </PageHeader>

  {#if error}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>{/if}

  {#if loading}
    <!-- Skeleton summary cards -->
    <div class="grid grid-cols-3 gap-3.5 mb-5">
      {#each [1,2,3] as _}
        <div class="bg-gray-900 border border-gray-800 rounded-2xl p-5 animate-pulse">
          <div class="h-3 w-20 bg-gray-800 rounded mb-3"></div>
          <div class="h-8 w-16 bg-gray-800 rounded mb-3"></div>
          <div class="h-1.5 w-full bg-gray-800 rounded-full"></div>
        </div>
      {/each}
    </div>
    <LoadingSkeleton variant="table" rows={5} />
  {:else if volumes.length === 0}
    <div class="text-center py-20 text-gray-600">
      <div class="text-5xl mb-4">💾</div>
      <p class="text-lg">볼륨이 없습니다</p>
      <button onclick={() => showModal = true} class="text-blue-400 hover:text-blue-300 text-sm mt-2 inline-block">첫 볼륨을 생성하세요 →</button>
    </div>
  {:else}
    <!-- Summary cards -->
    <div class="grid grid-cols-3 gap-3.5 mb-5">
      <!-- Card 1: 총 할당 -->
      <div class="bg-gray-900 border border-gray-800 rounded-2xl p-5">
        <div class="text-[11px] uppercase tracking-wider text-gray-500 font-medium mb-2">총 할당</div>
        <div class="text-[26px] font-bold text-white leading-none mb-1">{totalGb} <span class="text-[14px] font-normal text-gray-400">GB</span></div>
        <div class="text-[11px] text-gray-500 mb-3">{volumes.length}개 볼륨</div>
        <div class="h-1.5 bg-gray-800 rounded-full overflow-hidden">
          <div class="h-full bg-blue-500 rounded-full transition-all" style="width: {Math.min(100, totalGb / 10)}%"></div>
        </div>
      </div>
      <!-- Card 2: 연결된 볼륨 -->
      <div class="bg-gray-900 border border-gray-800 rounded-2xl p-5">
        <div class="text-[11px] uppercase tracking-wider text-gray-500 font-medium mb-2">연결된 볼륨</div>
        <div class="text-[26px] font-bold text-white leading-none mb-1">
          {attachedCount} <span class="text-[14px] font-normal text-gray-400">/ {volumes.length}</span>
        </div>
        <div class="text-[11px] text-gray-500">{attachedGb} GB 사용 중</div>
      </div>
      <!-- Card 3: 스냅샷 -->
      <div class="bg-gray-900 border border-gray-800 rounded-2xl p-5">
        <div class="text-[11px] uppercase tracking-wider text-gray-500 font-medium mb-2">스냅샷</div>
        <div class="text-[26px] font-bold text-white leading-none mb-1">{snapshots.length}</div>
        <div class="text-[11px] text-gray-500">최근 24시간 {recentSnapshots.length}개</div>
      </div>
    </div>

    <!-- Tab UI -->
    <div class="flex gap-1 mb-4 border-b border-gray-800">
      <button onclick={() => tab = 'volumes'}
        class="px-4 py-2 text-[13px] font-medium border-b-2 -mb-px transition-colors {tab === 'volumes' ? 'border-blue-500 text-white' : 'border-transparent text-gray-400 hover:text-gray-200'}">
        볼륨 {volumes.length}
      </button>
      <button onclick={() => tab = 'snapshots'}
        class="px-4 py-2 text-[13px] font-medium border-b-2 -mb-px transition-colors {tab === 'snapshots' ? 'border-blue-500 text-white' : 'border-transparent text-gray-400 hover:text-gray-200'}">
        스냅샷 {snapshots.length}
      </button>
    </div>

    {#if tab === 'volumes'}
      <!-- Volume custom table -->
      <div class="bg-[#0B1220] border border-gray-800 rounded-[10px] overflow-hidden">
        <!-- Header -->
        <div class="grid grid-cols-[1.6fr_80px_100px_110px_1.2fr_110px_auto] px-4 py-2.5 border-b border-gray-800 text-[11px] uppercase tracking-wider text-gray-500 font-medium">
          <div>이름</div>
          <div>크기</div>
          <div>유형</div>
          <div>상태</div>
          <div>연결</div>
          <div>부트</div>
          <div></div>
        </div>
        <!-- Rows -->
        {#each volumes as vol (vol.id)}
          <div
            onclick={() => openVolumePanel(vol.id)}
            onkeydown={(e) => e.key === 'Enter' && openVolumePanel(vol.id)}
            tabindex="0"
            role="button"
            class="grid grid-cols-[1.6fr_80px_100px_110px_1.2fr_110px_auto] px-4 py-3 text-[13px] items-center border-b border-gray-800 hover:bg-gray-800/30 transition-colors cursor-pointer last:border-b-0 {selectedVolumeId === vol.id ? 'bg-gray-800/30' : ''}"
          >
            <!-- 이름 -->
            <div class="flex items-center gap-2.5 min-w-0">
              <div class="shrink-0 w-7 h-7 rounded-md bg-cyan-500/15 border border-cyan-500/30 flex items-center justify-center">
                <svg class="w-3.5 h-3.5 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2" />
                </svg>
              </div>
              <div class="min-w-0">
                {#if vol.name}
                  <div class="text-white font-medium truncate">{vol.name}</div>
                {:else}
                  <div class="text-gray-400 font-mono text-xs truncate">{vol.id}</div>
                {/if}
                <div class="text-[11px] text-gray-500 font-mono truncate">{vol.id.slice(0, 8)}…</div>
              </div>
            </div>
            <!-- 크기 -->
            <div class="text-gray-300 font-mono text-[12px]">{formatStorage(vol.size)}</div>
            <!-- 유형 badge -->
            <div>
              <span class="text-[11px] px-2 py-0.5 rounded-md bg-gray-800 border border-gray-700 text-gray-300 font-mono">
                {vol.volume_type ?? '기본'}
              </span>
            </div>
            <!-- 상태 -->
            <div><StatusChip status={vol.status} /></div>
            <!-- 연결 -->
            <div class="text-[12px]">
              {#if vol.attachments.length > 0}
                <span class="text-blue-400">{vol.attachments.length}개 연결</span>
              {:else}
                <span class="text-gray-500">미연결</span>
              {/if}
            </div>
            <!-- 부트 badge -->
            <div>
              {#if vol.attachments.some((a: Record<string, unknown>) => a.device === '/dev/vda' || a.device === '/dev/sda')}
                <span class="text-[11px] px-2 py-0.5 rounded-md bg-blue-900/30 border border-blue-800 text-blue-400">부트</span>
              {/if}
            </div>
            <!-- 액션 -->
            <div class="flex items-center justify-end gap-1" onclick={(e) => e.stopPropagation()} role="none">
              <!-- 자동 백업 토글 -->
              <button
                onclick={(e) => { e.stopPropagation(); toggleAutoBackup(vol.id); }}
                disabled={autoBackupToggling === vol.id}
                title={autoBackupConfigs.has(vol.id) ? '자동 백업 비활성화' : '자동 백업 활성화'}
                class="relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out disabled:opacity-50 {autoBackupConfigs.has(vol.id) ? 'bg-blue-600' : 'bg-gray-700'}"
              >
                <span class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out {autoBackupConfigs.has(vol.id) ? 'translate-x-4' : 'translate-x-0'}"></span>
              </button>
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
          </div>
        {/each}
      </div>
    {:else}
      <!-- Snapshots custom table -->
      {#if snapshots.length === 0}
        <div class="text-center py-16 text-gray-600">
          <p class="text-sm">스냅샷이 없습니다</p>
        </div>
      {:else}
        <div class="bg-[#0B1220] border border-gray-800 rounded-[10px] overflow-hidden">
          <!-- Header -->
          <div class="grid grid-cols-[1.6fr_1.2fr_80px_140px_110px] px-4 py-2.5 border-b border-gray-800 text-[11px] uppercase tracking-wider text-gray-500 font-medium">
            <div>이름</div>
            <div>원본 볼륨</div>
            <div>크기</div>
            <div>생성됨</div>
            <div>상태</div>
          </div>
          <!-- Rows -->
          {#each snapshots as snap (snap.id)}
            <div class="grid grid-cols-[1.6fr_1.2fr_80px_140px_110px] px-4 py-3 text-[13px] items-center border-b border-gray-800 hover:bg-gray-800/30 transition-colors last:border-b-0">
              <div class="min-w-0">
                <div class="text-white font-medium truncate">{snap.name || snap.id.slice(0, 12)}</div>
                <div class="text-[11px] text-gray-500 font-mono truncate">{snap.id.slice(0, 8)}…</div>
              </div>
              <div class="text-gray-400 font-mono text-[12px] truncate">{snap.volume_id.slice(0, 12)}…</div>
              <div class="text-gray-300 font-mono text-[12px]">{snap.size} GB</div>
              <div class="text-gray-400 text-[12px]">
                {snap.created_at ? new Date(snap.created_at).toLocaleString('ko-KR', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—'}
              </div>
              <div><StatusChip status={snap.status} /></div>
            </div>
          {/each}
        </div>
      {/if}
    {/if}
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
