<script lang="ts">
  import { untrack } from 'svelte';
  import { auth } from '$lib/stores/auth';
  import { api, ApiError } from '$lib/api/client';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
  import PageHeader from '$lib/components/ui/PageHeader.svelte';
  import StatusChip from '$lib/components/ui/StatusChip.svelte';
  import LibraryUsageChart from '$lib/components/LibraryUsageChart.svelte';
  import { buildLibraryGraph } from '$lib/utils/librariesGraph';
  import LibraryDependencyGraph from '$lib/components/admin/libraries/LibraryDependencyGraph.svelte';
  import LibraryCard from '$lib/components/admin/libraries/LibraryCard.svelte';
  import FileStorageList from '$lib/components/admin/libraries/FileStorageList.svelte';
  import BuildDetailModal from '$lib/components/admin/libraries/BuildDetailModal.svelte';
  import type { LibraryConfig, FileStorage, TsPoint, LibraryBuild } from '$lib/types/libraries';

  let libraries = $state<LibraryConfig[]>([]);
  let fileStorages = $state<FileStorage[]>([]);
  let builds = $state<LibraryBuild[]>([]);
  let loading = $state(true);
  let refreshing = $state(false);
  let error = $state('');
  let message = $state('');
  let buildingId = $state<string | null>(null);
  let usageData = $state<TsPoint[]>([]);
  let usageRange = $state('7d');

  // 빌드 상세 모달
  let selectedBuildId = $state<number | null>(null);
  let buildDetailOpen = $state(false);

  const TERMINAL_STATUSES = new Set(['complete', 'error', 'timeout', 'cancelled']);

  const token = $derived($auth.token ?? undefined);
  const projectId = $derived($auth.projectId ?? undefined);
  const activeBuilds = $derived(builds.filter(b => !TERMINAL_STATUSES.has(b.status)));
  const layout = $derived(buildLibraryGraph(libraries, getBuildStatus));

  async function loadBuilds() {
    try {
      builds = await api.get<LibraryBuild[]>(
        '/api/admin/libraries/builds',
        token,
        projectId,
        { refresh: true },
      );
    } catch {
      // 빌드 목록 로드 실패 시 무시 (메인 데이터에 영향 없음)
    }
  }

  async function loadData() {
    if (libraries.length === 0) loading = true;
    else refreshing = true;
    error = '';
    await Promise.allSettled([
      api.get<LibraryConfig[]>('/api/libraries', token, projectId)
        .then(v => { libraries = v; loading = false; })
        .catch(e => { error = e instanceof ApiError ? e.message : '데이터 로드 실패'; loading = false; }),
      api.get<FileStorage[]>('/api/admin/file-storage', token, projectId)
        .then(v => { fileStorages = v; })
        .catch(() => {}),
      loadBuilds(),
    ]);
    loading = false;
    refreshing = false;
  }

  // 활성 빌드가 있으면 10초, 없으면 30초 폴링
  $effect(() => {
    const interval = setInterval(loadBuilds, activeBuilds.length > 0 ? 10_000 : 30_000);
    return () => clearInterval(interval);
  });

  function openBuildDetail(build: LibraryBuild) {
    selectedBuildId = build.id;
    buildDetailOpen = true;
  }

  function fmtRelative(iso: string | null | undefined): string {
    if (!iso) return '—';
    // timezone suffix 없는 UTC naive datetime을 로컬 시간으로 오해석하는 것을 방지
    const utcIso = iso.endsWith('Z') || iso.includes('+') ? iso : iso + 'Z';
    const ms = Date.now() - new Date(utcIso).getTime();
    const s = Math.floor(ms / 1000);
    if (s < 60) return `${s}초 전`;
    const m = Math.floor(s / 60);
    if (m < 60) return `${m}분 전`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h}시간 전`;
    return `${Math.floor(h / 24)}일 전`;
  }

  async function loadUsage(range: string) {
    try {
      usageData = await api.get<TsPoint[]>(`/api/admin/timeseries/library_usage?range=${range}`, token, projectId);
    } catch {
      usageData = [];
    }
  }

  $effect(() => {
    if (!token) return;
    untrack(() => {
      loadData();
      loadUsage(usageRange);
    });
  });

  function getStorageForLibrary(lib: LibraryConfig): FileStorage | null {
    return fileStorages.find(
      fs => fs.library_name === lib.id && fs.library_version === lib.version
    ) ?? null;
  }

  function getBuildStatus(lib: LibraryConfig): string {
    const fs = getStorageForLibrary(lib);
    if (!fs) return 'none';

    // union_status 메타데이터를 1순위로 판단
    const unionStatus = fs.metadata?.union_status;
    if (unionStatus) {
      if (unionStatus === 'ready') return 'ready';
      if (unionStatus === 'building' || unionStatus === 'pending') return 'building';
      if (unionStatus === 'error' || unionStatus === 'indeterminate') return 'failed';
      if (unionStatus === 'cancelled') return 'none';
    }

    // union_status 없을 때 Manila share status 폴백
    if (fs.status === 'available') return 'ready';
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

  function scrollToCard(id: string) {
    document.getElementById(`lib-card-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
</script>

<div class="flex flex-col h-full overflow-auto bg-gray-900 text-gray-100 p-6">
  <PageHeader title="라이브러리 관리" breadcrumb="라이브러리">
    {#snippet actions()}
      <div class="flex items-center gap-2">
        <button onclick={loadData} class="text-xs text-gray-400 hover:text-white transition-colors px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600 flex items-center gap-1.5">새로고침</button>
      </div>
    {/snippet}
  </PageHeader>

  {#if error}
    <div class="mb-4 p-3 bg-red-900/40 border border-red-700 rounded-md text-red-300 text-sm">{error}</div>
  {/if}
  {#if message}
    <div class="mb-4 p-3 bg-green-900/40 border border-green-700 rounded-md text-green-300 text-sm">{message}</div>
  {/if}

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
    <div class:opacity-60={refreshing} class:pointer-events-none={refreshing}>
      <div class="mb-6">
        <LibraryDependencyGraph {layout} onNodeClick={scrollToCard} />
      </div>

      <!-- 빌드 현황 -->
      {#if builds.length > 0}
        <div class="mb-6">
          <h3 class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">빌드 현황</h3>
          <div class="bg-gray-800 border border-gray-700 rounded-xl overflow-hidden">
            <table class="w-full text-sm">
              <thead>
                <tr class="border-b border-gray-700 text-xs text-gray-500 uppercase tracking-wide">
                  <th class="text-left px-4 py-2.5">라이브러리</th>
                  <th class="text-left px-4 py-2.5">상태</th>
                  <th class="text-left px-4 py-2.5 hidden md:table-cell">단계</th>
                  <th class="text-left px-4 py-2.5 w-36 hidden lg:table-cell">진행률</th>
                  <th class="text-left px-4 py-2.5 hidden xl:table-cell">VM 인스턴스</th>
                  <th class="text-left px-4 py-2.5 hidden lg:table-cell">시작</th>
                  <th class="px-4 py-2.5"></th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-700/50">
                {#each builds as build (build.id)}
                  {@const isDone = TERMINAL_STATUSES.has(build.status)}
                  <tr
                    class="hover:bg-gray-700/30 transition-colors cursor-pointer {isDone ? 'opacity-50' : ''}"
                    onclick={() => openBuildDetail(build)}
                  >
                    <td class="px-4 py-2.5 font-medium text-white">{build.library_id}</td>
                    <td class="px-4 py-2.5">
                      <StatusChip status={build.status} />
                    </td>
                    <td class="px-4 py-2.5 text-gray-400 text-xs hidden md:table-cell max-w-40 truncate">
                      {build.progress_step || '—'}
                    </td>
                    <td class="px-4 py-2.5 hidden lg:table-cell">
                      <div class="flex items-center gap-2">
                        <div class="flex-1 h-1 bg-gray-700 rounded-full overflow-hidden">
                          <div
                            class="h-full rounded-full {build.status === 'complete' ? 'bg-green-500' : build.status === 'error' ? 'bg-red-500' : 'bg-blue-500'}"
                            style="width:{build.progress_pct}%"
                          ></div>
                        </div>
                        <span class="text-xs text-gray-500 w-8 text-right">{build.progress_pct}%</span>
                      </div>
                    </td>
                    <td class="px-4 py-2.5 text-gray-500 text-xs font-mono hidden xl:table-cell">
                      {build.server_id ? build.server_id.slice(0, 8) + '…' : '—'}
                    </td>
                    <td class="px-4 py-2.5 text-gray-500 text-xs hidden lg:table-cell">
                      {fmtRelative(build.started_at)}
                    </td>
                    <td class="px-4 py-2.5 text-right">
                      <button
                        onclick={(e) => { e.stopPropagation(); openBuildDetail(build); }}
                        class="text-xs text-blue-400 hover:text-blue-300 transition-colors"
                      >상세</button>
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        </div>
      {/if}

      <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {#each libraries as lib}
          {@const buildStatus = getBuildStatus(lib)}
          {@const latestMount = usageData.length > 0 ? usageData[usageData.length - 1]?.[lib.name] : undefined}
          <LibraryCard
            {lib}
            {buildStatus}
            {latestMount}
            isBuilding={buildingId === lib.id}
            onTriggerBuild={triggerBuild}
          />
        {/each}
      </div>

      {#if fileStorages.length > 0}
        <FileStorageList {fileStorages} />
      {/if}
    </div>
  {/if}
</div>

<BuildDetailModal
  buildId={selectedBuildId}
  bind:open={buildDetailOpen}
  onCancelled={() => { loadBuilds(); loadData(); }}
/>
