<script lang="ts">
  import { goto } from '$app/navigation';
  import { auth, isAdmin } from '$lib/stores/auth';
  import { api, ApiError } from '$lib/api/client';
  import PageHeader from '$lib/components/ui/PageHeader.svelte';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';

  interface LayerInfo {
    id: string;
    name: string;
    version: string;
    sealed: boolean;
  }

  let name = $state('');
  let version = $state('');
  let parentId = $state('');
  let ubuntuBase = $state('');
  let contentHash = $state('');
  let sealedLayers = $state<LayerInfo[]>([]);
  let loadingParents = $state(true);
  let submitting = $state(false);
  let error = $state('');

  const token = $derived($auth.token ?? undefined);
  const projectId = $derived($auth.projectId ?? undefined);

  // 관리자 전용 페이지: 비관리자는 카탈로그로 리다이렉트
  $effect(() => {
    if (!$isAdmin) goto('/dashboard/library');
  });

  $effect(() => {
    if (token) loadSealedLayers();
  });

  async function loadSealedLayers() {
    loadingParents = true;
    try {
      const all = await api.get<LayerInfo[]>('/api/union/layers?limit=200', token, projectId);
      sealedLayers = all.filter(l => l.sealed);
    } catch {
      // 부모 로드 실패는 무시 (선택 사항)
    } finally {
      loadingParents = false;
    }
  }

  async function handleSubmit(e: Event) {
    e.preventDefault();
    if (submitting) return;
    error = '';

    if (!name.trim() || !version.trim() || !contentHash.trim()) {
      error = '이름, 버전, Content Hash는 필수입니다.';
      return;
    }
    if (!contentHash.match(/^sha256:[0-9a-f]{64}$/)) {
      error = 'Content Hash 형식이 올바르지 않습니다. (sha256:<64hex>)';
      return;
    }

    submitting = true;
    try {
      const body: Record<string, unknown> = {
        name: name.trim(),
        version: version.trim(),
        content_hash: contentHash.trim(),
        build_recipe: {},
        installed_packages: {},
      };
      if (parentId) body.parent_id = parentId;
      if (ubuntuBase.trim()) body.ubuntu_base = ubuntuBase.trim();

      const result = await api.post<LayerInfo>('/api/union/layers', body, token, projectId);
      goto(`/dashboard/library/${encodeURIComponent(result.id)}`);
    } catch (e) {
      error = e instanceof ApiError ? e.message : '레이어 생성 실패';
    } finally {
      submitting = false;
    }
  }
</script>

<div class="flex flex-col h-full overflow-auto bg-gray-900 text-gray-100 p-6">
  <PageHeader title="새 레이어 등록" breadcrumb="라이브러리 / 생성">
    {#snippet action()}
      <a href="/dashboard/library" class="text-sm text-gray-400 hover:text-gray-200">← 목록으로</a>
    {/snippet}
  </PageHeader>

  <div class="max-w-lg">
    {#if error}
      <div class="mb-4 p-3 bg-red-900/40 border border-red-700 rounded-md text-red-300 text-sm">{error}</div>
    {/if}

    <form onsubmit={handleSubmit} class="bg-gray-800 rounded-lg border border-gray-700 p-6 space-y-5">
      <div>
        <label class="block text-sm text-gray-400 mb-1" for="name">이름 <span class="text-red-400">*</span></label>
        <input
          id="name"
          type="text"
          bind:value={name}
          placeholder="예: python, cuda, pytorch"
          class="w-full px-3 py-2 text-sm bg-gray-700 border border-gray-600 rounded-md focus:outline-none focus:border-blue-500"
          required
        />
      </div>

      <div>
        <label class="block text-sm text-gray-400 mb-1" for="version">버전 <span class="text-red-400">*</span></label>
        <input
          id="version"
          type="text"
          bind:value={version}
          placeholder="예: 3.12, 12.3, 2.4.0"
          class="w-full px-3 py-2 text-sm bg-gray-700 border border-gray-600 rounded-md focus:outline-none focus:border-blue-500"
          required
        />
      </div>

      <div>
        <label class="block text-sm text-gray-400 mb-1" for="contentHash">Content Hash <span class="text-red-400">*</span></label>
        <input
          id="contentHash"
          type="text"
          bind:value={contentHash}
          placeholder="sha256:0000...0000"
          class="w-full px-3 py-2 text-sm bg-gray-700 border border-gray-600 rounded-md font-mono focus:outline-none focus:border-blue-500"
          required
        />
        <p class="text-xs text-gray-500 mt-1">형식: sha256:&lt;64자리 16진수&gt;</p>
      </div>

      <div>
        <label class="block text-sm text-gray-400 mb-1" for="parent">부모 레이어 (선택)</label>
        {#if loadingParents}
          <div class="text-xs text-gray-500">봉인된 레이어 목록 로드 중...</div>
        {:else}
          <select
            id="parent"
            bind:value={parentId}
            class="w-full px-3 py-2 text-sm bg-gray-700 border border-gray-600 rounded-md focus:outline-none focus:border-blue-500"
          >
            <option value="">없음 (최상위 레이어)</option>
            {#each sealedLayers as l}
              <option value={l.id}>{l.name} ({l.version})</option>
            {/each}
          </select>
        {/if}
      </div>

      <div>
        <label class="block text-sm text-gray-400 mb-1" for="ubuntuBase">Ubuntu Base (선택)</label>
        <input
          id="ubuntuBase"
          type="text"
          bind:value={ubuntuBase}
          placeholder="예: ubuntu-24.04, ubuntu-22.04"
          class="w-full px-3 py-2 text-sm bg-gray-700 border border-gray-600 rounded-md focus:outline-none focus:border-blue-500"
        />
      </div>

      <div class="pt-2">
        <button
          type="submit"
          disabled={submitting}
          class="w-full py-2.5 text-sm font-medium bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-md transition-colors"
        >
          {submitting ? '등록 중...' : '레이어 등록'}
        </button>
      </div>
    </form>
  </div>
</div>
