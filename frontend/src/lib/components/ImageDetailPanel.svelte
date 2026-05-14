<script lang="ts">
  import { auth } from '$lib/stores/auth';
  import { api, ApiError } from '$lib/api/client';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
  import Button from '$lib/components/ui/Button.svelte';

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
    isAdmin?: boolean;
    onClose?: () => void;
    onDelete?: (id: string) => void;
  }

  let { imageId, isAdmin = false, onClose, onDelete }: Props = $props();

  let image = $state<ImageDetail | null>(null);
  let loading = $state(true);
  let error = $state('');
  let deleting = $state(false);
  let visibilityValue = $state('');
  let savingVisibility = $state(false);
  let visibilityError = $state('');
  let visibilitySuccess = $state(false);

  // 공유 멤버 관리
  interface ImageMember { member_id: string; status: string; created_at: string | null; }
  let members = $state<ImageMember[]>([]);
  let loadingMembers = $state(false);
  let newMemberId = $state('');
  let addingMember = $state(false);
  let memberError = $state('');
  let removingMember = $state<string | null>(null);

  const isOwner = $derived(image?.owner === $auth.projectId);
  const canEditMetadata = $derived(isOwner || isAdmin);

  // 메타데이터 편집 — admin 페이지는 /api/admin/images/.../properties, 일반은 /api/images/.../properties
  const propertiesEndpoint = $derived(isAdmin ? '/api/admin/images' : '/api/images');

  // Glance 예약 키 (편집/삭제 금지) — 백엔드 _is_protected_key 와 동기화
  const RESERVED_KEYS = new Set([
    'id', 'name', 'status', 'visibility', 'owner', 'size', 'virtual_size',
    'disk_format', 'container_format', 'checksum', 'os_hash_algo', 'os_hash_value',
    'min_disk', 'min_ram', 'tags', 'self', 'file', 'schema', 'direct_url',
    'locations', 'created_at', 'updated_at', 'protected', 'os_hidden',
  ]);
  const isReservedKey = (k: string) => RESERVED_KEYS.has(k) || k.startsWith('os_glance_');

  let editingProps = $state(false);
  let propsDraft = $state<Record<string, string>>({});
  let propsRemovedKeys = $state<Set<string>>(new Set());
  let newPropKey = $state('');
  let newPropValue = $state('');
  let savingProps = $state(false);
  let propsError = $state('');

  function startEditProps() {
    if (!image) return;
    propsDraft = { ...image.properties };
    propsRemovedKeys = new Set();
    newPropKey = '';
    newPropValue = '';
    propsError = '';
    editingProps = true;
  }

  function cancelEditProps() {
    editingProps = false;
    propsDraft = {};
    propsRemovedKeys = new Set();
    propsError = '';
  }

  function removeProperty(key: string) {
    if (isReservedKey(key)) return;
    delete propsDraft[key];
    propsDraft = { ...propsDraft };
    propsRemovedKeys.add(key);
    propsRemovedKeys = new Set(propsRemovedKeys);
  }

  function addProperty() {
    const key = newPropKey.trim();
    const value = newPropValue.trim();
    if (!key) {
      propsError = '키를 입력하세요.';
      return;
    }
    if (isReservedKey(key)) {
      propsError = `"${key}" 는 시스템 예약 키라 편집할 수 없습니다.`;
      return;
    }
    propsDraft[key] = value;
    propsDraft = { ...propsDraft };
    propsRemovedKeys.delete(key);
    propsRemovedKeys = new Set(propsRemovedKeys);
    newPropKey = '';
    newPropValue = '';
    propsError = '';
  }

  async function saveProperties() {
    if (!image) return;
    // 추가 인풋에 값이 남아있으면 자동 commit (UX 함정 제거)
    const pendingKey = newPropKey.trim();
    if (pendingKey && !isReservedKey(pendingKey)) {
      propsDraft[pendingKey] = newPropValue.trim();
      propsDraft = { ...propsDraft };
      propsRemovedKeys.delete(pendingKey);
      propsRemovedKeys = new Set(propsRemovedKeys);
      newPropKey = '';
      newPropValue = '';
    }
    const original = image.properties;
    const setObj: Record<string, string> = {};
    for (const [k, v] of Object.entries(propsDraft)) {
      if (isReservedKey(k)) continue;
      if (original[k] !== v) setObj[k] = v;
    }
    const removeList = Array.from(propsRemovedKeys).filter((k) => !isReservedKey(k));
    if (Object.keys(setObj).length === 0 && removeList.length === 0) {
      editingProps = false;
      return;
    }
    savingProps = true;
    propsError = '';
    try {
      const updated = await api.patch<ImageDetail>(
        `${propertiesEndpoint}/${image.id}/properties`,
        { set: setObj, remove: removeList },
        $auth.token ?? undefined,
        $auth.projectId ?? undefined,
      );
      image = { ...image, properties: updated.properties };
      editingProps = false;
    } catch (e) {
      propsError = e instanceof ApiError ? e.message : '저장 실패';
    } finally {
      savingProps = false;
    }
  }

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
      if (image.visibility === 'shared') fetchMembers(image.id);
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
      if (updated.visibility === 'shared') fetchMembers(image.id);
    } catch (e) {
      visibilityError = e instanceof ApiError ? e.message : '저장 실패';
    } finally {
      savingVisibility = false;
    }
  }

  async function fetchMembers(id: string) {
    loadingMembers = true;
    memberError = '';
    try {
      members = await api.get<ImageMember[]>(`/api/images/${id}/members`, $auth.token ?? undefined, $auth.projectId ?? undefined);
    } catch {
      members = [];
    } finally {
      loadingMembers = false;
    }
  }

  async function addMember() {
    if (!image || !newMemberId.trim()) return;
    addingMember = true;
    memberError = '';
    try {
      await api.post(`/api/images/${image.id}/members`, { member: newMemberId.trim() }, $auth.token ?? undefined, $auth.projectId ?? undefined);
      newMemberId = '';
      await fetchMembers(image.id);
    } catch (e) {
      memberError = e instanceof ApiError ? e.message : '멤버 추가 실패';
    } finally {
      addingMember = false;
    }
  }

  async function removeMember(memberId: string) {
    if (!image) return;
    removingMember = memberId;
    memberError = '';
    try {
      await api.delete(`/api/images/${image.id}/members/${memberId}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
      await fetchMembers(image.id);
    } catch (e) {
      memberError = e instanceof ApiError ? e.message : '멤버 삭제 실패';
    } finally {
      removingMember = null;
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
        <dl class="grid grid-cols-1 @3xl/panel:grid-cols-2 gap-x-6 gap-y-3">
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
          {#if isAdmin}
          <div class="col-span-2">
            <dt class="text-xs text-gray-500 mb-0.5">소유자 (Project ID)</dt>
            <dd class="text-xs text-gray-300 font-mono break-all">{image.owner ?? '-'}</dd>
          </div>
          {/if}
          {#if image.os_hash_algo}
            <div class="col-span-2">
              <dt class="text-xs text-gray-500 mb-0.5">해시 ({image.os_hash_algo})</dt>
              <dd class="text-xs text-gray-300 font-mono break-all">{image.os_hash_value ?? '-'}</dd>
            </div>
          {/if}
          {#if isAdmin && image.direct_url}
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
        <dl class="grid grid-cols-1 @3xl/panel:grid-cols-2 gap-x-6 gap-y-3">
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
        <dl class="grid grid-cols-1 @3xl/panel:grid-cols-2 gap-x-6 gap-y-3">
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
            <Button onclick={saveVisibility} disabled={savingVisibility || visibilityValue === image.visibility}>
              {savingVisibility ? '저장 중...' : '저장'}
            </Button>
            {#if visibilitySuccess}
              <span class="text-green-400 text-sm">저장됨</span>
            {/if}
            {#if visibilityError}
              <span class="text-red-400 text-sm">{visibilityError}</span>
            {/if}
          </div>
        </div>
      {/if}

      <!-- 공유 멤버 관리 (shared 이미지 소유자만) -->
      {#if image.visibility === 'shared' && isOwner}
        <div class="bg-gray-900 border border-gray-800 rounded-lg p-5">
          <h3 class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">공유 프로젝트 관리</h3>

          <!-- 멤버 추가 -->
          <div class="flex items-center gap-2 mb-4">
            <input
              bind:value={newMemberId}
              placeholder="프로젝트 ID 입력"
              class="flex-1 bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 font-mono"
              onkeydown={(e) => e.key === 'Enter' && addMember()}
            />
            <Button onclick={addMember} disabled={addingMember || !newMemberId.trim()} size="sm">
              {addingMember ? '추가 중...' : '+ 추가'}
            </Button>
          </div>

          {#if memberError}
            <p class="text-red-400 text-xs mb-3">{memberError}</p>
          {/if}

          <!-- 멤버 목록 -->
          {#if loadingMembers}
            <p class="text-gray-500 text-xs">불러오는 중...</p>
          {:else if members.length === 0}
            <p class="text-gray-500 text-xs">공유된 프로젝트가 없습니다.</p>
          {:else}
            <div class="space-y-1">
              {#each members as m (m.member_id)}
                <div class="flex items-center justify-between px-3 py-2 bg-gray-800 rounded-lg">
                  <div>
                    <span class="text-xs text-gray-300 font-mono">{m.member_id}</span>
                    <span class="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-gray-700 text-gray-400">{m.status}</span>
                  </div>
                  <button
                    onclick={() => removeMember(m.member_id)}
                    disabled={removingMember === m.member_id}
                    class="text-xs px-2 py-1 text-red-400 hover:text-red-300 disabled:text-gray-600 transition-colors"
                  >
                    {removingMember === m.member_id ? '삭제 중...' : '삭제'}
                  </button>
                </div>
              {/each}
            </div>
          {/if}
        </div>
      {/if}

      <!-- 추가 속성 -->
      {#if Object.keys(image.properties).length > 0 || canEditMetadata}
        <div class="bg-gray-900 border border-gray-800 rounded-lg p-5">
          <div class="flex items-center justify-between mb-3">
            <h3 class="text-xs font-semibold text-gray-400 uppercase tracking-wide">추가 속성 <span class="normal-case font-normal text-gray-600">({Object.keys(image.properties).length})</span></h3>
            {#if canEditMetadata && !editingProps}
              <button onclick={startEditProps} class="text-xs text-blue-400 hover:text-blue-300">편집</button>
            {/if}
          </div>

          {#if !editingProps}
            {#if Object.keys(image.properties).length === 0}
              <p class="text-xs text-gray-500">추가 속성이 없습니다.</p>
            {:else}
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
            {/if}
          {:else}
            <table class="w-full text-xs mb-3">
              <tbody>
                {#each Object.entries(propsDraft) as [k, v]}
                  <tr class="border-b border-gray-800/50">
                    <td class="py-1.5 pr-2 font-mono w-2/5 {isReservedKey(k) ? 'text-gray-600' : 'text-gray-400'}">
                      {k}{#if isReservedKey(k)}&nbsp;<span class="text-[10px] text-gray-600">(예약)</span>{/if}
                    </td>
                    <td class="py-1.5 pr-2">
                      {#if isReservedKey(k)}
                        <span class="text-gray-500 font-mono break-all">{v}</span>
                      {:else}
                        <input bind:value={propsDraft[k]}
                          class="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1 text-gray-300 font-mono text-xs focus:outline-none focus:border-blue-500" />
                      {/if}
                    </td>
                    <td class="py-1.5 text-right w-10">
                      {#if !isReservedKey(k)}
                        <button onclick={() => removeProperty(k)} class="text-red-400 hover:text-red-300 text-xs">삭제</button>
                      {/if}
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>

            <div class="flex gap-2 mb-3">
              <input bind:value={newPropKey} placeholder="키"
                class="flex-1 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-white font-mono focus:outline-none focus:border-blue-500"
                onkeydown={(e) => e.key === 'Enter' && addProperty()} />
              <input bind:value={newPropValue} placeholder="값"
                class="flex-1 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-white font-mono focus:outline-none focus:border-blue-500"
                onkeydown={(e) => e.key === 'Enter' && addProperty()} />
              <button onclick={addProperty} class="text-xs text-blue-400 hover:text-blue-300 px-2 shrink-0">+ 추가</button>
            </div>

            {#if propsError}
              <p class="text-red-400 text-xs mb-2">{propsError}</p>
            {/if}

            <div class="flex gap-2 justify-end">
              <button onclick={cancelEditProps} disabled={savingProps}
                class="text-xs text-gray-400 hover:text-white px-3 py-1 border border-gray-700 rounded disabled:opacity-50">취소</button>
              <button onclick={saveProperties} disabled={savingProps}
                class="text-xs text-white bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 px-3 py-1 rounded">
                {savingProps ? '저장 중...' : '저장'}
              </button>
            </div>
          {/if}
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
