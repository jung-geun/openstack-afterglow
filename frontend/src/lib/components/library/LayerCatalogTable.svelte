<script lang="ts">
  import { goto } from '$app/navigation';
  import type { LayerInfo } from '$lib/types/layer';
  import { formatLayerSize, layerHref } from '$lib/types/layer';
  import StatusChip from '$lib/components/ui/StatusChip.svelte';
  import Pagination from '$lib/components/ui/Pagination.svelte';

  let {
    layers,
    query,
    refreshing,
    currentPage,
    pageSize,
    onPrev,
    onNext,
  }: {
    layers: LayerInfo[];
    query: string;
    refreshing: boolean;
    currentPage: number;
    pageSize: number;
    onPrev: () => void;
    onNext: () => void;
  } = $props();

  type TreeNode = { layer: LayerInfo; depth: number };

  function buildTree(src: LayerInfo[]): TreeNode[] {
    const childrenMap = new Map<string | null, LayerInfo[]>();
    for (const l of src) {
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
    const inTree = new Set(result.map(n => n.layer.id));
    for (const l of src) {
      if (!inTree.has(l.id)) result.push({ layer: l, depth: 0 });
    }
    return result;
  }

  function formatDate(dt: string): string {
    return new Date(dt).toLocaleDateString('ko-KR', { year: 'numeric', month: '2-digit', day: '2-digit' });
  }

  const treeNodes = $derived(query ? layers.map(l => ({ layer: l, depth: 0 })) : buildTree(layers));
</script>

<div class:opacity-60={refreshing} class:pointer-events-none={refreshing}>
  <div class="rounded-lg border border-gray-700 overflow-hidden overflow-x-auto">
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
            class="transition-colors"
          >
            <td class="px-4 py-3">
              <div class="flex items-center gap-1" style="padding-left: {depth * 1.25}rem">
                {#if depth > 0}
                  <span class="text-gray-600 mr-1">└</span>
                {/if}
                <a href={layerHref(layer.id)} class="block flex-1 min-w-0 group" title={layer.name}>
                  <span class="block font-medium text-gray-100 group-hover:text-blue-400 transition-colors max-md:max-w-[66vw] max-md:truncate">{layer.name}</span>
                  <div class="text-xs text-gray-500">{layer.version}</div>
                </a>
              </div>
            </td>
            <td class="px-4 py-3">
              <StatusChip status={layer.sealed ? 'sealed' : 'draft'} />
            </td>
            <td class="px-4 py-3 hidden md:table-cell text-gray-400 text-xs">{layer.ubuntu_base ?? '-'}</td>
            <td class="px-4 py-3 hidden lg:table-cell text-gray-400 text-xs">{formatLayerSize(layer.size_bytes)}</td>
            <td class="px-4 py-3 hidden lg:table-cell text-gray-400 text-xs">{formatDate(layer.created_at)}</td>
            <td class="px-4 py-3 hidden xl:table-cell text-gray-500 text-xs">{layer.created_by}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
  <Pagination
    page={currentPage + 1}
    hasPrev={currentPage > 0}
    hasNext={layers.length >= pageSize}
    {onPrev}
    {onNext}
  />
</div>
