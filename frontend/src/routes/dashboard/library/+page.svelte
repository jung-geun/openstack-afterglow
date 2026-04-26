<script lang="ts">
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
    size_bytes: number | null;
    file_count: number | null;
  }

  let layers = $state<LayerInfo[]>([]);
  let loading = $state(true);
  let error = $state('');
  let nameFilter = $state('');
  let currentPage = $state(0);
  const pageSize = 50;

  const token = $derived($auth.token ?? undefined);
  const projectId = $derived($auth.projectId ?? undefined);

  async function loadLayers() {
    loading = true;
    error = '';
    try {
      const params = new URLSearchParams({ limit: String(pageSize), offset: String(currentPage * pageSize) });
      if (nameFilter) params.set('name', nameFilter);
      layers = await api.get<LayerInfo[]>(`/api/union/layers?${params}`, token, projectId);
    } catch (e) {
      error = e instanceof ApiError ? e.message : '레이어 로드 실패';
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    if (token) loadLayers();
  });

  function formatSize(bytes: number | null): string {
    if (bytes === null) return '-';
    if (bytes >= 1073741824) return `${(bytes / 1073741824).toFixed(1)} GB`;
    if (bytes >= 1048576) return `${(bytes / 1048576).toFixed(1)} MB`;
    return `${(bytes / 1024).toFixed(0)} KB`;
  }

  function formatDate(dt: string): string {
    return new Date(dt).toLocaleDateString('ko-KR', { year: 'numeric', month: '2-digit', day: '2-digit' });
  }

  function layerHref(id: string): string {
    return `/dashboard/library/${encodeURIComponent(id)}`;
  }

  function handleSearch() {
    currentPage = 0;
    loadLayers();
  }

  // 트리 구조 계산: parent_id 기반
  type TreeNode = { layer: LayerInfo; depth: number };

  function buildTree(layers: LayerInfo[]): TreeNode[] {
    const map = new Map(layers.map(l => [l.id, l]));
    const childrenMap = new Map<string | null, LayerInfo[]>();
    for (const l of layers) {
      const key = l.parent_id ?? null;
      if (!childrenMap.has(key)) childrenMap.set(key, []);
      childrenMap.get(key)!.push(l);
    }

    const result: TreeNode[] = [];
    function traverse(id: string | null, depth: number) {
      const children = childrenMap.get(id) ?? [];
      for (const child of children.sort((a, b) => a.name.localeCompare(b.name))) {
        result.push({ layer: child, depth });
        traverse(child.id, depth + 1);
      }
    }
    traverse(null, 0);
    // 트리에 포함 안 된 레이어 (부모가 현재 페이지에 없는 경우) 맨 뒤에 추가
    const inTree = new Set(result.map(n => n.layer.id));
    for (const l of layers) {
      if (!inTree.has(l.id)) result.push({ layer: l, depth: 0 });
    }
    return result;
  }

  const treeNodes = $derived(nameFilter ? layers.map(l => ({ layer: l, depth: 0 })) : buildTree(layers));
</script>

<div class="flex flex-col h-full overflow-auto bg-gray-900 text-gray-100 p-6">
  <PageHeader title="레이어 카탈로그" breadcrumb="라이브러리">
    {#snippet action()}
      <div class="flex items-center gap-2">
        {#if $isAdmin}
          <a
            href="/dashboard/library/create"
            class="px-3 py-1.5 text-sm bg-blue-600 hover:bg-blue-500 rounded-md transition-colors"
          >+ 새 레이어</a>
        {/if}
        <a
          href="/dashboard/library/templates"
          class="px-3 py-1.5 text-sm bg-gray-700 hover:bg-gray-600 rounded-md transition-colors"
        >템플릿</a>
        <button onclick={loadLayers} class="text-xs text-gray-400 hover:text-white transition-colors px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600 flex items-center gap-1.5">새로고침</button>
      </div>
    {/snippet}
  </PageHeader>

  <!-- 검색 -->
  <div class="mb-4 flex gap-2">
    <input
      type="text"
      bind:value={nameFilter}
      placeholder="이름으로 검색..."
      class="flex-1 max-w-xs px-3 py-1.5 text-sm bg-gray-800 border border-gray-700 rounded-md focus:outline-none focus:border-blue-500"
      onkeydown={(e) => e.key === 'Enter' && handleSearch()}
    />
    <button
      onclick={handleSearch}
      class="px-3 py-1.5 text-sm bg-gray-700 hover:bg-gray-600 rounded-md transition-colors"
    >검색</button>
    {#if nameFilter}
      <button
        onclick={() => { nameFilter = ''; handleSearch(); }}
        class="px-3 py-1.5 text-sm text-gray-400 hover:text-gray-200"
      >초기화</button>
    {/if}
  </div>

  {#if error}
    <div class="mb-4 p-3 bg-red-900/40 border border-red-700 rounded-md text-red-300 text-sm">{error}</div>
  {/if}

  {#if loading}
    <LoadingSkeleton rows={8} />
  {:else if layers.length === 0}
    <div class="flex flex-col items-center justify-center flex-1 text-gray-500">
      <svg class="w-12 h-12 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
      </svg>
      <p>레이어가 없습니다</p>
    </div>
  {:else}
    <div class="rounded-lg border border-gray-700 overflow-hidden">
      <table class="w-full text-sm">
        <thead class="bg-gray-800 text-gray-400 text-xs uppercase">
          <tr>
            <th class="px-4 py-3 text-left">이름 / 버전</th>
            <th class="px-4 py-3 text-left">상태</th>
            <th class="px-4 py-3 text-left hidden md:table-cell">Ubuntu Base</th>
            <th class="px-4 py-3 text-left hidden lg:table-cell">크기</th>
            <th class="px-4 py-3 text-left hidden lg:table-cell">생성일</th>
            <th class="px-4 py-3 text-left hidden xl:table-cell">생성자</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-700/50">
          {#each treeNodes as { layer, depth }}
            <tr
              class="hover:bg-gray-800/50 cursor-pointer transition-colors"
              onclick={() => goto(layerHref(layer.id))}
            >
              <td class="px-4 py-3">
                <div class="flex items-center gap-1" style="padding-left: {depth * 1.25}rem">
                  {#if depth > 0}
                    <span class="text-gray-600 mr-1">└</span>
                  {/if}
                  <div>
                    <div class="font-medium text-gray-100">{layer.name}</div>
                    <div class="text-xs text-gray-500">{layer.version}</div>
                  </div>
                </div>
              </td>
              <td class="px-4 py-3">
                <StatusChip status={layer.sealed ? 'sealed' : 'draft'} />
              </td>
              <td class="px-4 py-3 hidden md:table-cell text-gray-400 text-xs">{layer.ubuntu_base ?? '-'}</td>
              <td class="px-4 py-3 hidden lg:table-cell text-gray-400 text-xs">{formatSize(layer.size_bytes)}</td>
              <td class="px-4 py-3 hidden lg:table-cell text-gray-400 text-xs">{formatDate(layer.created_at)}</td>
              <td class="px-4 py-3 hidden xl:table-cell text-gray-500 text-xs">{layer.created_by}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    <!-- 페이지네이션 -->
    <div class="mt-4 flex items-center gap-2 text-sm text-gray-400">
      <button
        onclick={() => { currentPage = Math.max(0, currentPage - 1); loadLayers(); }}
        disabled={currentPage === 0}
        class="px-3 py-1 bg-gray-800 rounded disabled:opacity-40 hover:bg-gray-700 disabled:cursor-not-allowed"
      >이전</button>
      <span>페이지 {currentPage + 1}</span>
      <button
        onclick={() => { currentPage++; loadLayers(); }}
        disabled={layers.length < pageSize}
        class="px-3 py-1 bg-gray-800 rounded disabled:opacity-40 hover:bg-gray-700 disabled:cursor-not-allowed"
      >다음</button>
    </div>
  {/if}
</div>
