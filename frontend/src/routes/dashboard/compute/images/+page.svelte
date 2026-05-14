<script lang="ts">
  import { untrack } from 'svelte';
  import { auth } from '$lib/stores/auth';
  import { api, ApiError } from '$lib/api/client';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
  import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
  import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
  import ImageDetailPanel from '$lib/components/ImageDetailPanel.svelte';
  import ImageUploadModal from '$lib/components/ImageUploadModal.svelte';
  import SlidePanel from '$lib/components/SlidePanel.svelte';
  import StatusChip from '$lib/components/ui/StatusChip.svelte';
  import PageHeader from '$lib/components/ui/PageHeader.svelte';

  interface ImageInfo {
    id: string;
    name: string;
    status: string;
    size: number | null;
    min_disk: number;
    min_ram: number;
    disk_format: string | null;
    os_distro: string | null;
    created_at: string | null;
    owner: string | null;
    visibility: string | null;
  }

  const KNOWN_DISTROS = ['ubuntu', 'centos', 'rocky', 'debian', 'fedora-coreos', 'fedora', 'rhel', 'windows', 'cirros'];

  const OS_LOGOS: Record<string, string> = {
    ubuntu: '/logos/Ubuntu.png',
    centos: '/logos/CentOS.png',
    fedora: '/logos/Fedora.png',
    'fedora-coreos': '/logos/coreos.png',
    windows: '/logos/Windows.png',
    coreos: '/logos/coreos.png',
  };

  const OS_EMOJI: Record<string, string> = {
    rocky: '🪨',
    debian: '🌀',
    rhel: '🔴',
    cirros: '☁️',
  };

  const OS_LABELS: Record<string, string> = {
    ubuntu: 'Ubuntu', centos: 'CentOS', rocky: 'Rocky Linux',
    debian: 'Debian', 'fedora-coreos': 'Fedora CoreOS', fedora: 'Fedora',
    rhel: 'RHEL', windows: 'Windows', cirros: 'CirrOS',
  };

  function osLabel(distro: string | null): string {
    if (!distro) return '-';
    return OS_LABELS[distro] ?? distro.charAt(0).toUpperCase() + distro.slice(1);
  }

  let images = $state<ImageInfo[]>([]);
  let loading = $state(true);
  let refreshing = $state(false);
  let error = $state('');
  let deleting = $state<string | null>(null);
  let togglingId = $state<string | null>(null);
  let selectedImageId = $state<string | null>(null);

  function openImagePanel(id: string) {
    selectedImageId = id;
    history.pushState({ imageId: id }, '', `/dashboard/compute/images/${id}`);
  }

  function closeImagePanel() {
    selectedImageId = null;
    history.pushState({}, '', '/dashboard/compute/images');
  }

  function handleImageDeleted(id: string) {
    images = images.filter(img => img.id !== id);
  }

  // 필터/정렬
  let distroFilter = $state('all');
  let sortOrder = $state<'asc' | 'desc'>('desc'); // created_at 정렬

  // 편집 모달
  let editTarget = $state<ImageInfo | null>(null);
  let editForm = $state({ name: '', os_distro: '', os_type: '', min_disk: 0, min_ram: 0 });
  let saving = $state(false);
  let saveError = $state('');

  const filteredImages = $derived.by(() => {
    let list = [...images];
    if (distroFilter !== 'all') {
      if (distroFilter === 'other') {
        list = list.filter(img => !img.os_distro || !KNOWN_DISTROS.includes(img.os_distro));
      } else {
        list = list.filter(img => img.os_distro === distroFilter);
      }
    }
    list.sort((a, b) => {
      const da = a.created_at ?? '';
      const db = b.created_at ?? '';
      return sortOrder === 'desc' ? db.localeCompare(da) : da.localeCompare(db);
    });
    return list;
  });

  const distroGroups = $derived.by(() => {
    const counts: Record<string, number> = { all: images.length };
    for (const img of images) {
      const d = img.os_distro ?? 'other';
      const key = KNOWN_DISTROS.includes(d) ? d : 'other';
      counts[key] = (counts[key] ?? 0) + 1;
    }
    return counts;
  });

  async function fetchImages(opts?: { refresh?: boolean }) {
    try {
      images = await api.get<ImageInfo[]>('/api/images', $auth.token ?? undefined, $auth.projectId ?? undefined, opts);
      error = '';
    } catch (e) {
      error = e instanceof ApiError ? `조회 실패 (${e.status})` : '서버 오류';
    } finally {
      loading = false;
    }
  }

  async function deleteImage(id: string, name: string) {
    if (!confirm(`이미지 "${name}"을 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.`)) return;
    deleting = id;
    try {
      await api.delete(`/api/images/${id}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
      images = images.filter(img => img.id !== id);
    } catch (e) {
      alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
    } finally {
      deleting = null;
    }
  }

  async function toggleActivation(img: ImageInfo) {
    togglingId = img.id;
    try {
      const action = img.status === 'active' ? 'deactivate' : 'reactivate';
      await api.post(`/api/images/${img.id}/${action}`, {}, $auth.token ?? undefined, $auth.projectId ?? undefined);
      await fetchImages({ refresh: true });
    } catch (e) {
      alert('상태 변경 실패: ' + (e instanceof ApiError ? e.message : String(e)));
    } finally {
      togglingId = null;
    }
  }

  function openEdit(img: ImageInfo) {
    editTarget = img;
    editForm = {
      name: img.name,
      os_distro: img.os_distro ?? '',
      os_type: '',
      min_disk: img.min_disk,
      min_ram: img.min_ram,
    };
    saveError = '';
  }

  async function saveEdit() {
    if (!editTarget) return;
    saving = true;
    saveError = '';
    try {
      const body: Record<string, unknown> = {};
      if (editForm.name !== editTarget.name) body.name = editForm.name;
      if (editForm.os_distro !== (editTarget.os_distro ?? '')) body.os_distro = editForm.os_distro || null;
      if (editForm.os_type) body.os_type = editForm.os_type;
      if (editForm.min_disk !== editTarget.min_disk) body.min_disk = editForm.min_disk;
      if (editForm.min_ram !== editTarget.min_ram) body.min_ram = editForm.min_ram;
      if (Object.keys(body).length === 0) { editTarget = null; return; }
      const updated = await api.patch<ImageInfo>(`/api/images/${editTarget.id}`, body, $auth.token ?? undefined, $auth.projectId ?? undefined);
      images = images.map(img => img.id === updated.id ? updated : img);
      editTarget = null;
    } catch (e) {
      saveError = e instanceof ApiError ? e.message : '저장 실패';
    } finally {
      saving = false;
    }
  }

  function formatSize(bytes: number | null): string {
    if (!bytes) return '-';
    const gb = bytes / 1024 / 1024 / 1024;
    return gb >= 1 ? `${Math.round(gb * 10) / 10} GB` : `${Math.round(bytes / 1024 / 1024)} MB`;
  }

  function formatDate(s: string | null): string {
    if (!s) return '-';
    return s.slice(0, 10);
  }

  async function forceRefresh() {
    refreshing = true;
    try {
      await fetchImages({ refresh: true });
    } finally {
      refreshing = false;
    }
  }

  const ar = createAutoRefresh(() => fetchImages(), {
    storageKey: 'dashboard-compute-images',
    defaultActive: true,
    defaultInterval: 60,
    intervalOptions: [10, 15, 30, 60],
  });

  $effect(() => {
    const pid = $auth.projectId;
    if (!pid) return;
    untrack(() => fetchImages());
  });

  // 업로드 모달
  let showUploadModal = $state(false);
  let uploadInitialFile = $state<File | null>(null);

  // 페이지 드래그앤드롭
  let pageDragActive = $state(false);

  function hasFiles(e: DragEvent): boolean {
    const types = e.dataTransfer?.types;
    if (!types) return false;
    for (let i = 0; i < types.length; i++) if (types[i] === 'Files') return true;
    return false;
  }

  function onWindowDragEnter(e: DragEvent) {
    if (!hasFiles(e)) return;
    e.preventDefault();
    pageDragActive = true;
  }
  function onWindowDragOver(e: DragEvent) {
    if (!hasFiles(e)) return;
    e.preventDefault();
    pageDragActive = true;
  }
  function onWindowDragLeave(e: DragEvent) {
    if (!hasFiles(e)) return;
    if (e.clientX <= 0 || e.clientY <= 0 || e.clientX >= window.innerWidth || e.clientY >= window.innerHeight) {
      pageDragActive = false;
    }
  }
  function onWindowDrop(e: DragEvent) {
    if (!hasFiles(e)) return;
    e.preventDefault();
    pageDragActive = false;
    const f = e.dataTransfer?.files?.[0];
    if (f) {
      uploadInitialFile = f;
      showUploadModal = true;
    }
  }
</script>

<!-- 편집 모달 -->
{#if editTarget}
  <div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
       onclick={() => { editTarget = null; }}
       role="dialog" aria-modal="true" tabindex="-1"
       onkeydown={(e) => e.key === 'Escape' && (editTarget = null)}>
    <div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl"
         onclick={(e) => e.stopPropagation()}
         role="none" onkeydown={(e) => e.stopPropagation()}>
      <h2 class="text-lg font-semibold text-white mb-5">이미지 메타데이터 편집</h2>
      <div class="space-y-4">
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름
            <input bind:value={editForm.name} type="text" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
          </label>
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">OS Distro
            <input bind:value={editForm.os_distro} type="text" placeholder="ubuntu, centos, rocky..." class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
          </label>
        </div>
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">최소 디스크 (GB)
              <input bind:value={editForm.min_disk} type="number" min="0" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
            </label>
          </div>
          <div>
            <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">최소 RAM (MB)
              <input bind:value={editForm.min_ram} type="number" min="0" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
            </label>
          </div>
        </div>
      </div>
      {#if saveError}<div class="mt-3 text-red-400 text-xs">{saveError}</div>{/if}
      <div class="flex justify-end gap-3 mt-6">
        <button onclick={() => { editTarget = null; }} class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">취소</button>
        <button onclick={saveEdit} disabled={saving} class="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors">{saving ? '저장 중...' : '저장'}</button>
      </div>
    </div>
  </div>
{/if}

<svelte:window
  ondragenter={onWindowDragEnter}
  ondragover={onWindowDragOver}
  ondragleave={onWindowDragLeave}
  ondrop={onWindowDrop}
/>

{#if pageDragActive}
  <div class="fixed inset-0 z-40 bg-blue-900/20 border-2 border-dashed border-blue-500 pointer-events-none flex items-center justify-center">
    <div class="bg-gray-900 border border-blue-600 rounded-xl px-8 py-5 text-blue-300 text-base font-medium shadow-2xl">
      이미지 파일을 놓으면 업로드 모달이 열립니다
    </div>
  </div>
{/if}

<div class="p-4 md:p-8">
  <PageHeader breadcrumb="COMPUTE / IMAGES" title="이미지">
    {#snippet actions()}
      <AutoRefreshControl
        bind:active={ar.active}
        bind:intervalSeconds={ar.intervalSeconds}
        intervalOptions={ar.intervalOptions}
        refreshing={refreshing}
        onManualRefresh={forceRefresh}
      />
      <button
        onclick={() => sortOrder = sortOrder === 'desc' ? 'asc' : 'desc'}
        class="flex items-center gap-1.5 text-xs text-gray-400 hover:text-white px-3 py-1.5 rounded-lg border border-gray-700 hover:border-gray-600 transition-colors"
      >
        날짜 {sortOrder === 'desc' ? '↓ 최신순' : '↑ 오래된순'}
      </button>
      <button
        onclick={() => { uploadInitialFile = null; showUploadModal = true; }}
        class="flex items-center gap-1.5 text-xs text-white px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 transition-colors font-medium"
      >
        + 이미지 업로드
      </button>
    {/snippet}
  </PageHeader>

  {#if error}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>{/if}

  {#if loading}
    <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3.5">
      {#each Array(8) as _}
        <div class="animate-pulse h-32 bg-gray-900 border border-gray-800 rounded-2xl"></div>
      {/each}
    </div>
  {:else}
    <!-- OS 필터 탭 -->
    <div class="flex flex-wrap gap-2 mb-5">
      {#each [['all', '전체'], ...KNOWN_DISTROS.map(d => [d, osLabel(d)]), ['other', '기타']] as [key, label]}
        {@const count = distroGroups[key] ?? 0}
        {#if count > 0 || key === 'all'}
          <button
            onclick={() => distroFilter = key}
            class="px-3 py-1 rounded-full text-xs font-medium transition-colors {distroFilter === key ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'}"
          >
            {label} {count > 0 ? `(${count})` : ''}
          </button>
        {/if}
      {/each}
    </div>

    {#if filteredImages.length === 0}
      <div class="text-center py-20 text-gray-600">
        <p class="text-lg">이미지가 없습니다</p>
      </div>
    {:else}
      <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3.5">
        {#each filteredImages as img (img.id)}
          <div
            class="bg-gray-900 border border-gray-800 rounded-2xl p-4 flex flex-col gap-3 cursor-pointer hover:border-gray-600 transition-colors"
            onclick={() => openImagePanel(img.id)}
            role="button"
            tabindex="0"
            onkeydown={(e) => e.key === 'Enter' && openImagePanel(img.id)}
          >
            <!-- Header: icon + name -->
            <div class="flex items-center gap-2.5">
              <div class="w-10 h-10 rounded-lg bg-gray-800 border border-gray-700 flex items-center justify-center overflow-hidden shrink-0">
                {#if img.os_distro && OS_LOGOS[img.os_distro]}
                  <img src={OS_LOGOS[img.os_distro]} alt={img.os_distro} class="w-6 h-6 object-contain" />
                {:else if img.os_distro && OS_EMOJI[img.os_distro]}
                  <span class="text-lg">{OS_EMOJI[img.os_distro]}</span>
                {:else}
                  <span class="text-lg">💿</span>
                {/if}
              </div>
              <div class="flex-1 min-w-0">
                <div class="text-white text-[13px] font-medium truncate font-mono">{img.name}</div>
                <div class="text-[11px] text-gray-500 mt-0.5">{img.os_distro ? osLabel(img.os_distro) : 'Unknown'}</div>
              </div>
            </div>

            <!-- Footer: status + visibility + size -->
            <div class="flex items-center gap-2 text-[11px]">
              <StatusChip status={img.status} />
              {#if img.visibility === 'public'}
                <span class="px-1.5 py-0.5 rounded border text-[10px] font-medium bg-blue-900/25 border-blue-800 text-blue-400">공개</span>
              {:else if img.visibility === 'shared'}
                <span class="px-1.5 py-0.5 rounded border text-[10px] font-medium bg-teal-900/25 border-teal-800 text-teal-400">공유</span>
              {:else if img.visibility === 'community'}
                <span class="px-1.5 py-0.5 rounded border text-[10px] font-medium bg-teal-900/25 border-teal-800 text-teal-400">커뮤니티</span>
              {:else}
                <span class="px-1.5 py-0.5 rounded border text-[10px] font-medium bg-gray-800/70 border-gray-700 text-gray-400">비공개</span>
              {/if}
              <span class="ml-auto text-gray-500">{formatSize(img.size)}</span>
            </div>

            <!-- Actions (own images only) -->
            {#if img.owner === $auth.projectId}
              <div class="flex items-center gap-1 pt-1 border-t border-gray-800" role="none" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
                {#if img.status === 'active' || img.status === 'deactivated'}
                  <button
                    onclick={() => toggleActivation(img)}
                    disabled={togglingId === img.id}
                    class="text-[11px] {img.status === 'active' ? 'text-orange-400 hover:text-orange-300' : 'text-green-400 hover:text-green-300'} disabled:text-gray-600 transition-colors px-2 py-1 rounded hover:bg-gray-800"
                  >{togglingId === img.id ? '...' : img.status === 'active' ? '비활성화' : '활성화'}</button>
                {/if}
                <button
                  onclick={() => openEdit(img)}
                  class="text-[11px] text-blue-400 hover:text-blue-300 transition-colors px-2 py-1 rounded hover:bg-blue-900/30"
                >편집</button>
                <button
                  onclick={() => deleteImage(img.id, img.name)}
                  disabled={deleting === img.id}
                  class="text-[11px] text-red-400 hover:text-red-300 disabled:text-gray-600 transition-colors px-2 py-1 rounded hover:bg-red-900/30"
                >{deleting === img.id ? '삭제 중...' : '삭제'}</button>
              </div>
            {/if}
          </div>
        {/each}
      </div>
    {/if}
  {/if}
</div>

<ImageUploadModal
  bind:open={showUploadModal}
  token={$auth.token ?? undefined}
  projectId={$auth.projectId ?? undefined}
  initialFile={uploadInitialFile}
  onUploaded={() => fetchImages({ refresh: true })}
  onClose={() => { uploadInitialFile = null; }}
/>

{#if selectedImageId}
  <SlidePanel onClose={closeImagePanel} width="w-full md:w-[60vw] max-w-2xl">
    <ImageDetailPanel
      imageId={selectedImageId}
      onClose={closeImagePanel}
      onDelete={handleImageDeleted}
    />
  </SlidePanel>
{/if}
