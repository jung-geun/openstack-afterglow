<script lang="ts">
  import { auth } from '$lib/stores/auth';
  import { api, ApiError } from '$lib/api/client';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
  import RefreshButton from '$lib/components/RefreshButton.svelte';
  import AutoRefreshToggle from '$lib/components/AutoRefreshToggle.svelte';
  import StatusChip from '$lib/components/ui/StatusChip.svelte';
  import PageHeader from '$lib/components/ui/PageHeader.svelte';
  import LibraryUsageChart from '$lib/components/LibraryUsageChart.svelte';

  interface LibraryConfig {
    id: string;
    name: string;
    version: string;
    packages: string[];
    depends_on: string[];
    available_prebuilt: boolean;
    share_proto: string;
    visibility: string;
  }

  interface FileStorage {
    id: string;
    name: string;
    status: string;
    library_name: string | null;
    library_version: string | null;
    metadata: Record<string, string>;
  }

  interface TsPoint { ts: number; [key: string]: number | undefined; }

  let libraries = $state<LibraryConfig[]>([]);
  let fileStorages = $state<FileStorage[]>([]);
  let loading = $state(true);
  let error = $state('');
  let message = $state('');
  let buildingId = $state<string | null>(null);
  let autoRefresh = $state(false);
  let usageData = $state<TsPoint[]>([]);
  let usageRange = $state('7d');

  const token = $derived($auth.token ?? undefined);
  const projectId = $derived($auth.projectId ?? undefined);

  async function loadData() {
    loading = true;
    error = '';
    try {
      [libraries, fileStorages] = await Promise.all([
        api.get<LibraryConfig[]>('/api/libraries', token, projectId),
        api.get<FileStorage[]>('/api/admin/file-storage', token, projectId),
      ]);
    } catch (e) {
      error = e instanceof ApiError ? e.message : '데이터 로드 실패';
    } finally {
      loading = false;
    }
  }

  async function loadUsage(range: string) {
    try {
      usageData = await api.get<TsPoint[]>(`/api/admin/timeseries/library_usage?range=${range}`, token, projectId);
    } catch {
      usageData = [];
    }
  }

  $effect(() => {
    if (token) {
      loadData();
      loadUsage(usageRange);
    }
  });

  // 라이브러리에 해당하는 FileStorage 찾기
  function getStorageForLibrary(lib: LibraryConfig): FileStorage | null {
    return fileStorages.find(
      fs => fs.library_name === lib.name && fs.library_version === lib.version
    ) ?? null;
  }

  // 빌드 상태 계산
  function getBuildStatus(lib: LibraryConfig): string {
    const fs = getStorageForLibrary(lib);
    if (!fs) return 'none';
    const unionStatus = fs.metadata?.union_status ?? fs.status;
    if (unionStatus === 'available' || fs.status === 'available') return 'ready';
    if (fs.status === 'creating' || fs.status === 'extending') return 'building';
    if (fs.status === 'error') return 'failed';
    return fs.status;
  }

  async function triggerBuild(lib: LibraryConfig) {
    if (buildingId) return;
    buildingId = lib.id;
    message = '';
    error = '';
    try {
      await api.post(`/api/admin/file-storage/build?library_id=${encodeURIComponent(lib.id)}&auto_install=true`, {}, token, projectId);
      message = `${lib.name} 빌드를 시작했습니다.`;
      await loadData();
    } catch (e) {
      if (e instanceof ApiError) {
        if (e.status === 409) {
          error = `${lib.name}: 이미 빌드된 파일 스토리지가 존재합니다. 재빌드하려면 기존 스토리지를 삭제 후 다시 시도하세요.`;
        } else if (e.status === 400) {
          error = `${lib.name} 빌드 설정 오류: ${e.message}`;
        } else if (e.status === 404) {
          error = `${lib.name}: 라이브러리를 찾을 수 없습니다.`;
        } else {
          error = `${lib.name} 빌드 실패 (${e.status}): ${e.message}`;
        }
      } else {
        error = `${lib.name} 빌드 트리거 실패: 네트워크 오류가 발생했습니다.`;
      }
    } finally {
      buildingId = null;
    }
  }

  // 빌드 상태에 따른 StatusChip 색상 매핑
  function statusLabel(status: string): string {
    const map: Record<string, string> = {
      ready: 'ready',
      building: 'building',
      failed: 'error',
      none: 'none',
    };
    return map[status] ?? status;
  }

  function statusText(status: string): string {
    const map: Record<string, string> = {
      ready: '빌드 완료',
      building: '빌드 중',
      failed: '빌드 실패',
      none: '미빌드',
    };
    return map[status] ?? status;
  }

  // 의존성 그래프 SVG 계산
  let showGraph = $state(false);

  interface GraphNode {
    id: string;
    name: string;
    level: number;
    posX: number;
    posY: number;
    status: string;
  }

  interface GraphEdge {
    from: string;
    to: string;
  }

  const graphData = $derived.by(() => {
    if (libraries.length === 0) return { nodes: [] as GraphNode[], edges: [] as GraphEdge[], width: 0, height: 0 };

    // 레벨 계산 (BFS)
    const levels: Record<string, number> = {};
    function calcLevel(id: string): number {
      if (levels[id] !== undefined) return levels[id];
      const lib = libraries.find(l => l.id === id);
      if (!lib || lib.depends_on.length === 0) {
        levels[id] = 0;
        return 0;
      }
      levels[id] = Math.max(...lib.depends_on.map(dep => calcLevel(dep) + 1));
      return levels[id];
    }
    libraries.forEach(l => calcLevel(l.id));

    // 레벨별 노드 그룹화
    const byLevel: Record<number, LibraryConfig[]> = {};
    libraries.forEach(l => {
      const lv = levels[l.id] ?? 0;
      if (!byLevel[lv]) byLevel[lv] = [];
      byLevel[lv].push(l);
    });

    const nodeW = 130, nodeH = 36, hGap = 60, vGap = 20, padX = 20, padY = 20;
    const maxLv = Math.max(...Object.keys(byLevel).map(Number));

    const nodes: GraphNode[] = [];
    for (let lv = 0; lv <= maxLv; lv++) {
      const group = byLevel[lv] ?? [];
      group.forEach((lib, idx) => {
        nodes.push({
          id: lib.id,
          name: lib.name,
          level: lv,
          posX: padX + lv * (nodeW + hGap),
          posY: padY + idx * (nodeH + vGap),
          status: getBuildStatus(lib),
        });
      });
    }

    const edges: GraphEdge[] = [];
    libraries.forEach(lib => {
      lib.depends_on.forEach(dep => {
        edges.push({ from: dep, to: lib.id });
      });
    });

    const totalW = padX * 2 + (maxLv + 1) * (nodeW + hGap) - hGap;
    const maxNodesPerLevel = Math.max(...Object.values(byLevel).map(g => g.length));
    const totalH = padY * 2 + maxNodesPerLevel * (nodeH + vGap) - vGap;

    return { nodes, edges, width: totalW, height: totalH, nodeW, nodeH };
  });

  function nodeColor(status: string): string {
    const map: Record<string, string> = {
      ready: '#16a34a',
      building: '#2563eb',
      failed: '#dc2626',
      none: '#4b5563',
    };
    return map[status] ?? '#4b5563';
  }

  function scrollToCard(id: string) {
    document.getElementById(`lib-card-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
</script>

<div class="flex flex-col h-full overflow-auto bg-gray-900 text-gray-100 p-6">
  <PageHeader title="라이브러리 관리" breadcrumb="라이브러리">
    {#snippet action()}
      <div class="flex items-center gap-2">
        <AutoRefreshToggle bind:enabled={autoRefresh} interval={10000} onTick={loadData} />
        <RefreshButton onclick={loadData} />
      </div>
    {/snippet}
  </PageHeader>

  {#if error}
    <div class="mb-4 p-3 bg-red-900/40 border border-red-700 rounded-md text-red-300 text-sm">{error}</div>
  {/if}
  {#if message}
    <div class="mb-4 p-3 bg-green-900/40 border border-green-700 rounded-md text-green-300 text-sm">{message}</div>
  {/if}

  <!-- 라이브러리 사용량 차트 -->
  <div class="mb-6">
    <LibraryUsageChart
      data={usageData}
      title="라이브러리 사용 현황 (활성 VM 기준)"
      currentRange={usageRange}
      onRangeChange={(r) => { usageRange = r; loadUsage(r); }}
    />
  </div>

  {#if loading}
    <LoadingSkeleton rows={6} />
  {:else if libraries.length === 0}
    <div class="flex flex-col items-center justify-center flex-1 text-gray-500">
      <p>등록된 라이브러리가 없습니다</p>
    </div>
  {:else}
    <!-- 의존성 그래프 -->
    <div class="mb-6 bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
      <button
        class="w-full flex items-center justify-between px-4 py-3 text-sm text-gray-300 hover:text-white hover:bg-gray-700/50 transition-colors"
        onclick={() => showGraph = !showGraph}
      >
        <span class="font-medium">의존성 그래프</span>
        <span class="text-gray-500 text-xs">{showGraph ? '▲ 접기' : '▼ 펼치기'}</span>
      </button>
      {#if showGraph}
        <div class="px-4 pb-4 overflow-x-auto">
          <svg
            width={graphData.width}
            height={graphData.height}
            class="min-w-full"
          >
            <defs>
              <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
                <polygon points="0 0, 8 3, 0 6" fill="#6b7280" />
              </marker>
            </defs>
            <!-- 엣지 -->
            {#each graphData.edges as edge}
              {@const fromNode = graphData.nodes.find(n => n.id === edge.from)}
              {@const toNode = graphData.nodes.find(n => n.id === edge.to)}
              {#if fromNode && toNode}
                <line
                  x1={fromNode.posX + (graphData.nodeW ?? 130)}
                  y1={fromNode.posY + (graphData.nodeH ?? 36) / 2}
                  x2={toNode.posX}
                  y2={toNode.posY + (graphData.nodeH ?? 36) / 2}
                  stroke="#4b5563"
                  stroke-width="1.5"
                  marker-end="url(#arrowhead)"
                />
              {/if}
            {/each}
            <!-- 노드 -->
            {#each graphData.nodes as node}
              <g
                class="cursor-pointer"
                onclick={() => scrollToCard(node.id)}
                role="button"
                tabindex="0"
                onkeydown={(e) => e.key === 'Enter' && scrollToCard(node.id)}
              >
                <rect
                  x={node.posX}
                  y={node.posY}
                  width={graphData.nodeW ?? 130}
                  height={graphData.nodeH ?? 36}
                  rx="6"
                  fill="#1f2937"
                  stroke={nodeColor(node.status)}
                  stroke-width="1.5"
                />
                <circle
                  cx={node.posX + 12}
                  cy={node.posY + (graphData.nodeH ?? 36) / 2}
                  r="4"
                  fill={nodeColor(node.status)}
                />
                <text
                  x={node.posX + 22}
                  y={node.posY + (graphData.nodeH ?? 36) / 2 + 4}
                  fill="#e5e7eb"
                  font-size="11"
                  font-family="system-ui, sans-serif"
                >{node.name}</text>
              </g>
            {/each}
          </svg>
          <div class="flex items-center gap-4 mt-3 text-xs text-gray-500">
            {#each [['ready','#16a34a','빌드 완료'], ['building','#2563eb','빌드 중'], ['failed','#dc2626','빌드 실패'], ['none','#4b5563','미빌드']] as [, color, label]}
              <span class="flex items-center gap-1">
                <span class="inline-block w-2 h-2 rounded-full" style="background:{color}"></span>{label}
              </span>
            {/each}
          </div>
        </div>
      {/if}
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      {#each libraries as lib}
        {@const buildStatus = getBuildStatus(lib)}
        <div id="lib-card-{lib.id}" class="bg-gray-800 rounded-lg border border-gray-700 p-5 flex flex-col gap-4">
          <div class="flex items-start justify-between">
            <div>
              <h3 class="font-semibold text-gray-100">{lib.name}</h3>
              <p class="text-xs text-gray-500 mt-0.5">v{lib.version}</p>
            </div>
            <div class="flex flex-col items-end gap-1">
              <StatusChip status={statusLabel(buildStatus)} label={statusText(buildStatus)} />
              <div class="flex items-center gap-1">
                <span class="text-xs text-gray-600">{lib.share_proto ?? 'CEPHFS'}</span>
                <span class="px-1.5 py-0.5 text-xs rounded {lib.visibility === 'private' ? 'bg-gray-700 text-gray-400' : 'bg-green-900/30 text-green-500'}">
                  {lib.visibility === 'private' ? '비공개' : '공개'}
                </span>
              </div>
            </div>
          </div>

          {#if lib.depends_on && lib.depends_on.length > 0}
            <div>
              <p class="text-xs text-gray-500 mb-1.5">의존성</p>
              <div class="flex flex-wrap gap-1">
                {#each lib.depends_on as dep}
                  <span class="px-2 py-0.5 text-xs bg-gray-700 text-gray-300 rounded-full">{dep}</span>
                {/each}
              </div>
            </div>
          {/if}

          {#if lib.packages && lib.packages.length > 0}
            <div>
              <p class="text-xs text-gray-500 mb-1.5">패키지 ({lib.packages.length})</p>
              <div class="flex flex-wrap gap-1">
                {#each lib.packages.slice(0, 5) as pkg}
                  <span class="px-2 py-0.5 text-xs bg-gray-700/50 text-gray-400 rounded">{pkg}</span>
                {/each}
                {#if lib.packages.length > 5}
                  <span class="px-2 py-0.5 text-xs text-gray-600">+{lib.packages.length - 5}개</span>
                {/if}
              </div>
            </div>
          {/if}

          <div class="mt-auto pt-3 border-t border-gray-700">
            <button
              onclick={() => triggerBuild(lib)}
              disabled={buildingId === lib.id || buildStatus === 'building'}
              class="w-full py-1.5 text-sm bg-blue-700 hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed rounded-md transition-colors"
            >
              {buildingId === lib.id ? '요청 중...' : buildStatus === 'building' ? '빌드 중...' : buildStatus === 'ready' ? '재빌드' : '빌드 시작'}
            </button>
          </div>
        </div>
      {/each}
    </div>

    <!-- 전체 FileStorage 목록 (관리자 확인용) -->
    {#if fileStorages.length > 0}
      <div class="mt-8">
        <h2 class="text-sm font-medium text-gray-400 mb-3">프리빌트 Share 목록 ({fileStorages.length})</h2>
        <div class="rounded-lg border border-gray-700 overflow-hidden">
          <table class="w-full text-sm">
            <thead class="bg-gray-800 text-gray-400 text-xs uppercase">
              <tr>
                <th class="px-4 py-3 text-left">이름</th>
                <th class="px-4 py-3 text-left">라이브러리</th>
                <th class="px-4 py-3 text-left">상태</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-700/50">
              {#each fileStorages as fs}
                <tr class="hover:bg-gray-800/50">
                  <td class="px-4 py-3 text-gray-300 text-xs font-mono">{fs.name}</td>
                  <td class="px-4 py-3 text-gray-400 text-xs">
                    {fs.library_name ?? '-'}
                    {#if fs.library_version}<span class="text-gray-600"> v{fs.library_version}</span>{/if}
                  </td>
                  <td class="px-4 py-3"><StatusChip status={fs.status} /></td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      </div>
    {/if}
  {/if}
</div>
