<script lang="ts">
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { auth, isAdmin } from '$lib/stores/auth';
  import { api, ApiError } from '$lib/api/client';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
  import StatusChip from '$lib/components/ui/StatusChip.svelte';
  import PageHeader from '$lib/components/ui/PageHeader.svelte';

  interface LayerInfo {
    id: string;
    name: string;
    version: string;
    created_at: string;
    created_by: string;
    sealed: boolean;
    parent_id: string | null;
    ubuntu_base: string | null;
    build_recipe: Record<string, unknown>;
    installed_packages: Record<string, unknown>;
    content_hash: string;
    size_bytes: number | null;
    file_count: number | null;
  }

  interface AncestorChain {
    layers: LayerInfo[];
  }

  const layerId = $derived($page.params.id);
  const encodedId = $derived(encodeURIComponent(layerId));

  let layer = $state<LayerInfo | null>(null);
  let ancestors = $state<LayerInfo[]>([]);
  let dependents = $state<LayerInfo[]>([]);
  let loading = $state(true);
  let error = $state('');
  let sealing = $state(false);
  let deleting = $state(false);
  let showRecipe = $state(false);
  let showPackages = $state(false);
  let confirmDelete = $state(false);

  const token = $derived($auth.token ?? undefined);
  const projectId = $derived($auth.projectId ?? undefined);

  async function loadData() {
    loading = true;
    error = '';
    await Promise.allSettled([
      api.get<LayerInfo>(`/api/union/layers/${encodedId}`, token, projectId)
        .then(v => { layer = v; loading = false; })
        .catch(e => { error = e instanceof ApiError ? e.message : '레이어 로드 실패'; loading = false; }),
      api.get<AncestorChain>(`/api/union/layers/${encodedId}/ancestors`, token, projectId)
        .then(v => { ancestors = v.layers; })
        .catch(() => {}),
      api.get<LayerInfo[]>(`/api/union/layers/${encodedId}/dependents`, token, projectId)
        .then(v => { dependents = v; })
        .catch(() => {}),
    ]);
    loading = false;
  }

  $effect(() => {
    if (token && layerId) loadData();
  });

  async function sealLayer() {
    if (!layer || sealing) return;
    sealing = true;
    try {
      await api.post(`/api/union/layers/${encodedId}/seal`, {}, token, projectId);
      layer = { ...layer, sealed: true };
    } catch (e) {
      error = e instanceof ApiError ? e.message : '봉인 실패';
    } finally {
      sealing = false;
    }
  }

  async function deleteLayer() {
    if (!layer || deleting) return;
    deleting = true;
    try {
      await api.delete(`/api/union/layers/${encodedId}`, token, projectId);
      goto('/dashboard/library');
    } catch (e) {
      error = e instanceof ApiError ? e.message : '삭제 실패';
      confirmDelete = false;
    } finally {
      deleting = false;
    }
  }

  function formatSize(bytes: number | null): string {
    if (bytes === null) return '-';
    if (bytes >= 1073741824) return `${(bytes / 1073741824).toFixed(1)} GB`;
    if (bytes >= 1048576) return `${(bytes / 1048576).toFixed(1)} MB`;
    return `${(bytes / 1024).toFixed(0)} KB`;
  }

  function formatDate(dt: string): string {
    return new Date(dt).toLocaleString('ko-KR');
  }

  function layerHref(id: string): string {
    return `/dashboard/library/${encodeURIComponent(id)}`;
  }
</script>

<div class="flex flex-col h-full overflow-auto bg-gray-900 text-gray-100 p-6">
  <PageHeader title={layer?.name ?? '레이어 상세'} breadcrumb="라이브러리">
    {#snippet action()}
      <a href="/dashboard/library" class="text-sm text-gray-400 hover:text-gray-200">← 목록으로</a>
    {/snippet}
  </PageHeader>

  {#if error}
    <div class="mb-4 p-3 bg-red-900/40 border border-red-700 rounded-md text-red-300 text-sm">{error}</div>
  {/if}

  {#if loading}
    <LoadingSkeleton rows={6} />
  {:else if layer}
    <div class="grid grid-cols-1 xl:grid-cols-3 gap-6">
      <!-- 레이어 정보 -->
      <div class="xl:col-span-2 space-y-6">
        <div class="bg-gray-800 rounded-lg border border-gray-700 p-5">
          <div class="flex items-center justify-between mb-4">
            <div>
              <h2 class="text-lg font-semibold">{layer.name}</h2>
              <p class="text-sm text-gray-400">버전: {layer.version}</p>
            </div>
            <StatusChip status={layer.sealed ? 'sealed' : 'draft'} />
          </div>
          <dl class="grid grid-cols-2 gap-3 text-sm">
            <div>
              <dt class="text-gray-500">Content Hash</dt>
              <dd class="font-mono text-xs text-gray-300 break-all mt-1">{layer.content_hash}</dd>
            </div>
            <div>
              <dt class="text-gray-500">Ubuntu Base</dt>
              <dd class="text-gray-300 mt-1">{layer.ubuntu_base ?? '-'}</dd>
            </div>
            <div>
              <dt class="text-gray-500">크기</dt>
              <dd class="text-gray-300 mt-1">{formatSize(layer.size_bytes)}</dd>
            </div>
            <div>
              <dt class="text-gray-500">파일 수</dt>
              <dd class="text-gray-300 mt-1">{layer.file_count ?? '-'}</dd>
            </div>
            <div>
              <dt class="text-gray-500">생성일</dt>
              <dd class="text-gray-300 mt-1">{formatDate(layer.created_at)}</dd>
            </div>
            <div>
              <dt class="text-gray-500">생성자</dt>
              <dd class="text-gray-300 mt-1">{layer.created_by}</dd>
            </div>
          </dl>

          <!-- 관리자 액션 -->
          {#if $isAdmin}
            <div class="mt-5 pt-4 border-t border-gray-700 flex items-center gap-3">
              {#if !layer.sealed}
                <button
                  onclick={sealLayer}
                  disabled={sealing}
                  class="px-3 py-1.5 text-sm bg-amber-700 hover:bg-amber-600 disabled:opacity-50 rounded-md transition-colors"
                >
                  {sealing ? '봉인 중...' : '🔒 봉인'}
                </button>
              {/if}
              {#if !confirmDelete}
                <button
                  onclick={() => confirmDelete = true}
                  class="px-3 py-1.5 text-sm bg-red-900/40 hover:bg-red-800/60 text-red-400 hover:text-red-300 border border-red-800 rounded-md transition-colors"
                >삭제</button>
              {:else}
                <span class="text-sm text-red-400">정말 삭제하시겠습니까?</span>
                <button
                  onclick={deleteLayer}
                  disabled={deleting}
                  class="px-3 py-1.5 text-sm bg-red-700 hover:bg-red-600 disabled:opacity-50 rounded-md"
                >{deleting ? '삭제 중...' : '확인'}</button>
                <button
                  onclick={() => confirmDelete = false}
                  class="px-3 py-1.5 text-sm bg-gray-700 hover:bg-gray-600 rounded-md"
                >취소</button>
              {/if}
            </div>
          {/if}
        </div>

        <!-- 설치된 패키지 -->
        {#if Object.keys(layer.installed_packages).length > 0}
          <div class="bg-gray-800 rounded-lg border border-gray-700">
            <button
              class="w-full flex items-center justify-between px-5 py-3 text-sm font-medium"
              onclick={() => showPackages = !showPackages}
            >
              <span>설치된 패키지 ({Object.keys(layer.installed_packages).length})</span>
              <span class="text-gray-400">{showPackages ? '▲' : '▼'}</span>
            </button>
            {#if showPackages}
              <div class="px-5 pb-4 border-t border-gray-700">
                <pre class="text-xs text-gray-300 overflow-auto max-h-64 mt-3">{JSON.stringify(layer.installed_packages, null, 2)}</pre>
              </div>
            {/if}
          </div>
        {/if}

        <!-- 빌드 레시피 -->
        {#if Object.keys(layer.build_recipe).length > 0}
          <div class="bg-gray-800 rounded-lg border border-gray-700">
            <button
              class="w-full flex items-center justify-between px-5 py-3 text-sm font-medium"
              onclick={() => showRecipe = !showRecipe}
            >
              <span>빌드 레시피</span>
              <span class="text-gray-400">{showRecipe ? '▲' : '▼'}</span>
            </button>
            {#if showRecipe}
              <div class="px-5 pb-4 border-t border-gray-700">
                <pre class="text-xs text-gray-300 overflow-auto max-h-64 mt-3">{JSON.stringify(layer.build_recipe, null, 2)}</pre>
              </div>
            {/if}
          </div>
        {/if}
      </div>

      <!-- 우측: 조상 체인 + 자식 레이어 -->
      <div class="space-y-6">
        <!-- 조상 체인 -->
        <div class="bg-gray-800 rounded-lg border border-gray-700 p-5">
          <h3 class="text-sm font-medium text-gray-300 mb-4">조상 체인 (base → leaf)</h3>
          {#if ancestors.length === 0}
            <p class="text-sm text-gray-500">최상위 레이어</p>
          {:else}
            <div class="relative">
              {#each ancestors as anc, i}
                <div class="flex items-center gap-2 py-2 {i < ancestors.length - 1 ? 'border-b border-gray-700' : ''}">
                  <div class="flex flex-col items-center mr-2">
                    <div class="w-2 h-2 rounded-full {anc.id === layer.id ? 'bg-blue-400' : 'bg-gray-600'}"></div>
                    {#if i < ancestors.length - 1}
                      <div class="w-0.5 h-4 bg-gray-700 mt-1"></div>
                    {/if}
                  </div>
                  <div class="flex-1 min-w-0">
                    {#if anc.id === layer.id}
                      <div class="text-sm font-medium text-blue-400">{anc.name}</div>
                      <div class="text-xs text-blue-400/60">{anc.version} · 현재</div>
                    {:else}
                      <a href={layerHref(anc.id)} class="text-sm text-gray-300 hover:text-white">{anc.name}</a>
                      <div class="text-xs text-gray-500">{anc.version}</div>
                    {/if}
                  </div>
                  <StatusChip status={anc.sealed ? 'sealed' : 'draft'} />
                </div>
              {/each}
            </div>
          {/if}
        </div>

        <!-- 자식 레이어 -->
        <div class="bg-gray-800 rounded-lg border border-gray-700 p-5">
          <h3 class="text-sm font-medium text-gray-300 mb-4">파생 레이어 ({dependents.length})</h3>
          {#if dependents.length === 0}
            <p class="text-sm text-gray-500">파생된 레이어 없음</p>
          {:else}
            <div class="space-y-2">
              {#each dependents as dep}
                <a
                  href={layerHref(dep.id)}
                  class="flex items-center justify-between p-2 rounded bg-gray-700/40 hover:bg-gray-700 transition-colors"
                >
                  <div>
                    <div class="text-sm text-gray-200">{dep.name}</div>
                    <div class="text-xs text-gray-500">{dep.version}</div>
                  </div>
                  <StatusChip status={dep.sealed ? 'sealed' : 'draft'} />
                </a>
              {/each}
            </div>
          {/if}
        </div>
      </div>
    </div>
  {:else}
    <p class="text-gray-400">레이어를 찾을 수 없습니다.</p>
  {/if}
</div>
