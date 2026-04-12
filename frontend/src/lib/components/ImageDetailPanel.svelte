<script lang="ts">
  import { auth } from '$lib/stores/auth';
  import { api, ApiError } from '$lib/api/client';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';

  interface ImageDetail {
    id: string;
    name: string;
    status: string;
    size: number | null;
    min_disk: number;
    min_ram: number;
    disk_format: string | null;
    os_type: string | null;
    os_distro: string | null;
    created_at: string | null;
    owner: string | null;
    visibility: string | null;
    checksum: string | null;
    container_format: string | null;
    virtual_size: number | null;
    updated_at: string | null;
    protected: boolean;
    tags: string[];
    properties: Record<string, string>;
    os_hash_algo: string | null;
    os_hash_value: string | null;
    direct_url: string | null;
  }

  const VISIBILITY_OPTIONS = [
    { value: 'public',    label: '공개 (Public)' },
    { value: 'private',   label: '비공개 (Private)' },
    { value: 'shared',    label: '공유 (Shared)' },
    { value: 'community', label: '커뮤니티 (Community)' },
  ];

  interface Props {
    imageId: string;
    onClose?: () => void;
    onDelete?: (id: string) => void;
  }

  let { imageId, onClose, onDelete }: Props = $props();

  let image = $state<ImageDetail | null>(null);
  let loading = $state(true);
  let error = $state('');
  let deleting = $state(false);
  let visibilityValue = $state('');
  let savingVisibility = $state(false);
  let visibilityError = $state('');
  let visibilitySuccess = $state(false);

  const isOwner = $derived(image?.owner === $auth.projectId);

  $effect(() => {
    if (!imageId || !$auth.token) return;
    loading = true;
    error = '';
    image = null;
    fetchImage(imageId);
  });

  async function fetchImage(id: string) {
    try {
      image = await api.get<ImageDetail>(
        `/api/images/${id}`,
        $auth.token ?? undefined,
        $auth.projectId ?? undefined
      );
      visibilityValue = image.visibility ?? '';
    } catch (e) {
      error = e instanceof ApiError ? `조회 실패 (${e.status}): ${e.message}` : '서버 오류';
    } finally {
      loading = false;
    }
  }

  async function saveVisibility() {
    if (!image || visibilityValue === image.visibility) return;
    savingVisibility = true;
    visibilityError = '';
    visibilitySuccess = false;
    try {
      const updated = await api.patch<ImageDetail>(
        `/api/images/${image.id}`,
        { visibility: visibilityValue },
        $auth.token ?? undefined,
        $auth.projectId ?? undefined
      );
      image = { ...image, visibility: updated.visibility };
      visibilitySuccess = true;
      setTimeout(() => { visibilitySuccess = false; }, 2000);
    } catch (e) {
      visibilityError = e instanceof ApiError ? e.message : '저장 실패';
    } finally {
      savingVisibility = false;
    }
  }

  async function deleteImage() {
    if (!image) return;
    if (!confirm(`이미지 "${image.name}"을 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.`)) return;
    deleting = true;
    try {
      await api.delete(`/api/images/${image.id}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
      onDelete?.(image.id);
      onClose?.();
    } catch (e) {
      alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
      deleting = false;
    }
  }

  function formatSize(bytes: number | null): string {
    if (!bytes) return '-';
    const gb = bytes / 1024 / 1024 / 1024;
    return gb >= 1 ? `${Math.round(gb * 10) / 10} GB` : `${Math.round(bytes / 1024 / 1024)} MB`;
  }

  function formatDate(s: string | null): string {
    if (!s) return '-';
    return s.replace('T', ' ').slice(0, 19);
  }

  function visibilityBadge(v: string | null) {
    switch (v) {
      case 'public':    return 'text-green-400 bg-green-900/30';
      case 'shared':    return 'text-blue-400 bg-blue-900/30';
      case 'community': return 'text-cyan-400 bg-cyan-900/30';
      default:          return 'text-gray-400 bg-gray-800';
    }
  }

  function visibilityLabel(v: string | null) {
    switch (v) {
      case 'public':    return '공개';
      case 'shared':    return '공유';
      case 'community': return '커뮤니티';
      case 'private':   return '비공개';
      default:          return v ?? '-';
    }
  }
</script>

<div class="flex flex-col h-full">
  <!-- 헤더 -->
  <div class="flex items-start justify-between px-6 py-4 border-b border-gray-800 shrink-0">
    <div class="min-w-0 pr-4">
      {#if image}
        <h2 class="text-lg font-bold text-white truncate">{image.name}</h2>
        <div class="flex items-center gap-2 mt-1.5 flex-wrap">
          <span class="px-2 py-0.5 rounded text-xs font-medium {image.status === 'active' ? 'text-green-400 bg-green-900/30' : 'text-gray-400 bg-gray-800'}">
            {image.status}
          </span>
          <span class="px-2 py-0.5 rounded text-xs font-medium {visibilityBadge(image.visibility)}">
            {visibilityLabel(image.visibility)}
          </span>
          {#if image.protected}
            <span class="px-2 py-0.5 rounded text-xs font-medium text-amber-400 bg-amber-900/30">보호됨</span>
          {/if}
        </div>
      {:else if loading}
        <div class="h-6 w-48 bg-gray-800 rounded animate-pulse"></div>
      {/if}
    </div>
    <button
      onclick={onClose}
      class="shrink-0 text-gray-400 hover:text-white transition-colors p-1 rounded hover:bg-gray-800"
      aria-label="닫기"
    >
      <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" viewBox="0 0 20 20" fill="currentColor">
        <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
      </svg>
    </button>
  </div>

  <!-- 본문 -->
  <div class="flex-1 overflow-y-auto px-6 py-5 space-y-4">
    {#if error}
      <div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">{error}</div>
    {:else if loading}
      <LoadingSkeleton variant="card" rows={5} />
    {:else if image}

      <!-- 기본 정보 -->
      <div class="bg-gray-900 border border-gray-800 rounded-lg p-5">
        <h3 class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">기본 정보</h3>
        <dl class="grid grid-cols-2 gap-x-6 gap-y-3">
          <div class="col-span-2">
            <dt class="text-xs text-gray-500 mb-0.5">ID</dt>
            <dd class="text-xs text-gray-300 font-mono break-all">{image.id}</dd>
          </div>
          <div>
            <dt class="text-xs text-gray-500 mb-0.5">OS 배포판</dt>
            <dd class="text-sm text-gray-300">{image.os_distro ?? '-'}</dd>
          </div>
          <div>
            <dt class="text-xs text-gray-500 mb-0.5">디스크 포맷</dt>
            <dd class="text-sm text-gray-300">{image.disk_format ?? '-'}</dd>
          </div>
          <div>
            <dt class="text-xs text-gray-500 mb-0.5">컨테이너 포맷</dt>
            <dd class="text-sm text-gray-300">{image.container_format ?? '-'}</dd>
          </div>
          <div>
            <dt class="text-xs text-gray-500 mb-0.5">보호됨</dt>
            <dd class="text-sm text-gray-300">{image.protected ? '예' : '아니요'}</dd>
          </div>
          {#if image.tags.length > 0}
            <div class="col-span-2">
              <dt class="text-xs text-gray-500 mb-0.5">태그</dt>
              <dd class="text-sm text-gray-300">{image.tags.join(', ')}</dd>
            </div>
          {/if}
          <div class="col-span-2">
            <dt class="text-xs text-gray-500 mb-0.5">소유자 (Project ID)</dt>
            <dd class="text-xs text-gray-300 font-mono break-all">{image.owner ?? '-'}</dd>
          </div>
          {#if image.os_hash_algo}
            <div class="col-span-2">
              <dt class="text-xs text-gray-500 mb-0.5">해시 ({image.os_hash_algo})</dt>
              <dd class="text-xs text-gray-300 font-mono break-all">{image.os_hash_value ?? '-'}</dd>
            </div>
          {/if}
          {#if image.direct_url}
            <div class="col-span-2">
              <dt class="text-xs text-gray-500 mb-0.5">저장 위치</dt>
              <dd class="text-xs text-gray-300 font-mono break-all">{image.direct_url}</dd>
            </div>
          {/if}
        </dl>
      </div>

      <!-- 크기 -->
      <div class="bg-gray-900 border border-gray-800 rounded-lg p-5">
        <h3 class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">크기 정보</h3>
        <dl class="grid grid-cols-2 gap-x-6 gap-y-3">
          <div>
            <dt class="text-xs text-gray-500 mb-0.5">크기</dt>
            <dd class="text-sm text-gray-300">{formatSize(image.size)}</dd>
          </div>
          <div>
            <dt class="text-xs text-gray-500 mb-0.5">가상 크기</dt>
            <dd class="text-sm text-gray-300">{formatSize(image.virtual_size)}</dd>
          </div>
          <div>
            <dt class="text-xs text-gray-500 mb-0.5">최소 디스크</dt>
            <dd class="text-sm text-gray-300">{image.min_disk} GB</dd>
          </div>
          <div>
            <dt class="text-xs text-gray-500 mb-0.5">최소 RAM</dt>
            <dd class="text-sm text-gray-300">{image.min_ram} MB</dd>
          </div>
        </dl>
      </div>

      <!-- 날짜 & 체크섬 -->
      <div class="bg-gray-900 border border-gray-800 rounded-lg p-5">
        <h3 class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">메타데이터</h3>
        <dl class="grid grid-cols-2 gap-x-6 gap-y-3">
          <div>
            <dt class="text-xs text-gray-500 mb-0.5">등록일</dt>
            <dd class="text-sm text-gray-300">{formatDate(image.created_at)}</dd>
          </div>
          <div>
            <dt class="text-xs text-gray-500 mb-0.5">수정일</dt>
            <dd class="text-sm text-gray-300">{formatDate(image.updated_at)}</dd>
          </div>
          {#if image.checksum}
            <div class="col-span-2">
              <dt class="text-xs text-gray-500 mb-0.5">체크섬 (MD5)</dt>
              <dd class="text-xs text-gray-300 font-mono break-all">{image.checksum}</dd>
            </div>
          {/if}
        </dl>
      </div>

      <!-- 공개 범위 수정 (소유한 이미지만) -->
      {#if isOwner}
        <div class="bg-gray-900 border border-gray-800 rounded-lg p-5">
          <h3 class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">공개 범위 수정</h3>
          <div class="flex items-center gap-3 flex-wrap">
            <select
              bind:value={visibilityValue}
              class="bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
            >
              {#each VISIBILITY_OPTIONS as opt}
                <option value={opt.value}>{opt.label}</option>
              {/each}
            </select>
            <button
              onclick={saveVisibility}
              disabled={savingVisibility || visibilityValue === image.visibility}
              class="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors"
            >
              {savingVisibility ? '저장 중...' : '저장'}
            </button>
            {#if visibilitySuccess}
              <span class="text-green-400 text-sm">저장됨</span>
            {/if}
            {#if visibilityError}
              <span class="text-red-400 text-sm">{visibilityError}</span>
            {/if}
          </div>
        </div>
      {/if}

      <!-- 추가 속성 -->
      {#if Object.keys(image.properties).length > 0}
        <div class="bg-gray-900 border border-gray-800 rounded-lg p-5">
          <h3 class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">추가 속성</h3>
          <table class="w-full text-xs">
            <tbody>
              {#each Object.entries(image.properties) as [k, v]}
                <tr class="border-b border-gray-800/50">
                  <td class="py-1.5 pr-4 text-gray-400 font-mono w-2/5">{k}</td>
                  <td class="py-1.5 text-gray-300 font-mono break-all">{v}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}

      <!-- 삭제 (소유한 이미지만) -->
      {#if isOwner}
        <div class="pt-2 pb-4">
          <button
            onclick={deleteImage}
            disabled={deleting}
            class="w-full py-2 text-sm text-red-400 hover:text-red-300 disabled:text-gray-600 border border-red-900 hover:border-red-700 disabled:border-gray-700 rounded-lg transition-colors"
          >
            {deleting ? '삭제 중...' : '이미지 삭제'}
          </button>
        </div>
      {/if}

    {/if}
  </div>
</div>
