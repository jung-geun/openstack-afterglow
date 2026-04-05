<script lang="ts">
  import { onMount } from 'svelte';
  import { auth } from '$lib/stores/auth';
  import { api, ApiError } from '$lib/api/client';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';

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
  }

  const KNOWN_DISTROS = ['ubuntu', 'centos', 'rocky', 'debian', 'fedora', 'rhel', 'windows', 'cirros'];

  let images = $state<ImageInfo[]>([]);
  let loading = $state(true);
  let error = $state('');

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

  async function fetchImages() {
    try {
      images = await api.get<ImageInfo[]>('/api/images', $auth.token ?? undefined, $auth.projectId ?? undefined);
      error = '';
    } catch (e) {
      error = e instanceof ApiError ? `조회 실패 (${e.status})` : '서버 오류';
    } finally {
      loading = false;
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

  onMount(fetchImages);
</script>

<!-- 편집 모달 -->
{#if editTarget}
  <div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
       onclick={() => { editTarget = null; }}
       role="dialog" aria-modal="true" tabindex="-1"
       onkeydown={(e) => e.key === 'Escape' && (editTarget = null)}>
    <div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl"
         onclick={(e) => e.stopPropagation()}
         role="document" onkeydown={(e) => e.stopPropagation()}>
      <h2 class="text-lg font-semibold text-white mb-5">이미지 메타데이터 편집</h2>
      <div class="space-y-4">
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름</label>
          <input bind:value={editForm.name} type="text" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">OS Distro</label>
          <input bind:value={editForm.os_distro} type="text" placeholder="ubuntu, centos, rocky..." class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
        </div>
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">최소 디스크 (GB)</label>
            <input bind:value={editForm.min_disk} type="number" min="0" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
          </div>
          <div>
            <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">최소 RAM (MB)</label>
            <input bind:value={editForm.min_ram} type="number" min="0" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
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

<div class="p-8">
  <div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold text-white">이미지</h1>
    <button
      onclick={() => sortOrder = sortOrder === 'desc' ? 'asc' : 'desc'}
      class="flex items-center gap-1.5 text-xs text-gray-400 hover:text-white px-3 py-1.5 rounded-lg border border-gray-700 hover:border-gray-600 transition-colors"
    >
      날짜 {sortOrder === 'desc' ? '↓ 최신순' : '↑ 오래된순'}
    </button>
  </div>

  {#if error}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>{/if}

  {#if loading}
    <LoadingSkeleton variant="table" rows={5} />
  {:else}
    <!-- OS 필터 탭 -->
    <div class="flex flex-wrap gap-2 mb-5">
      {#each [['all', '전체'], ...KNOWN_DISTROS.map(d => [d, d.charAt(0).toUpperCase() + d.slice(1)]), ['other', '기타']] as [key, label]}
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
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
              <th class="text-left py-3 pr-6">이름</th>
              <th class="text-left py-3 pr-6">OS</th>
              <th class="text-left py-3 pr-6">상태</th>
              <th class="text-left py-3 pr-6">포맷</th>
              <th class="text-left py-3 pr-6">크기</th>
              <th class="text-left py-3 pr-6">최소 디스크</th>
              <th class="text-left py-3 pr-6">등록일</th>
              <th class="text-left py-3"></th>
            </tr>
          </thead>
          <tbody>
            {#each filteredImages as img (img.id)}
              <tr class="border-b border-gray-800/50 hover:bg-gray-800/50 transition-colors">
                <td class="py-3 pr-6 font-medium text-white">{img.name}</td>
                <td class="py-3 pr-6 text-gray-400 text-xs">{img.os_distro ?? '-'}</td>
                <td class="py-3 pr-6">
                  <span class="px-2 py-0.5 rounded text-xs font-medium {img.status === 'active' ? 'text-green-400 bg-green-900/30' : 'text-gray-400 bg-gray-800'}">{img.status}</span>
                </td>
                <td class="py-3 pr-6 text-gray-400 text-xs">{img.disk_format ?? '-'}</td>
                <td class="py-3 pr-6 text-gray-400 text-xs">{formatSize(img.size)}</td>
                <td class="py-3 pr-6 text-gray-400 text-xs">{img.min_disk} GB</td>
                <td class="py-3 pr-6 text-gray-400 text-xs">{formatDate(img.created_at)}</td>
                <td class="py-3">
                  {#if img.owner === $auth.projectId}
                    <button
                      onclick={() => openEdit(img)}
                      class="text-xs text-blue-400 hover:text-blue-300 transition-colors px-2 py-1 rounded hover:bg-blue-900/30"
                    >편집</button>
                  {/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  {/if}
</div>
