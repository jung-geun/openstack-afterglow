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
  }

  let images = $state<ImageInfo[]>([]);
  let loading = $state(true);
  let error = $state('');

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

  onMount(fetchImages);
</script>

<div class="p-8">
  <div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold text-white">이미지</h1>
  </div>

  {#if error}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>{/if}

  {#if loading}
    <LoadingSkeleton variant="table" rows={5} />
  {:else if images.length === 0}
    <div class="text-center py-20 text-gray-600">
      <div class="text-5xl mb-4">🖼️</div>
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
          </tr>
        </thead>
        <tbody>
          {#each images as img (img.id)}
            <tr class="border-b border-gray-800/50 hover:bg-gray-800/50 transition-colors">
              <td class="py-3 pr-6 font-medium text-white">{img.name}</td>
              <td class="py-3 pr-6 text-gray-400 text-xs">{img.os_distro ?? '-'}</td>
              <td class="py-3 pr-6"><span class="px-2 py-0.5 rounded text-xs font-medium {img.status === 'active' ? 'text-green-400 bg-green-900/30' : 'text-gray-400 bg-gray-800'}">{img.status}</span></td>
              <td class="py-3 pr-6 text-gray-400 text-xs">{img.disk_format ?? '-'}</td>
              <td class="py-3 pr-6 text-gray-400 text-xs">{img.size ? Math.round(img.size / 1024 / 1024 / 1024 * 10) / 10 + ' GB' : '-'}</td>
              <td class="py-3 pr-6 text-gray-400 text-xs">{img.min_disk} GB</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
