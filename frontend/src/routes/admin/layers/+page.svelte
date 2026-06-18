<script lang="ts">
  import { untrack } from 'svelte';
  import { auth } from '$lib/stores/auth';
  import { api, ApiError } from '$lib/api/client';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
  import PageHeader from '$lib/components/ui/PageHeader.svelte';
  import StatusChip from '$lib/components/ui/StatusChip.svelte';
  import Modal from '$lib/components/ui/Modal.svelte';

  // ---------------------------------------------------------------------------
  // 타입
  // ---------------------------------------------------------------------------

  interface LayerBuild {
    id: number;
    layer_name: string;
    python_version: string;
    profile_name: string;
    share_id: string;
    server_id: string | null;
    port_id: string | null;
    build_token: string | null;
    cloud_init_status: string | null;
    status: string;
    progress_step: string;
    progress_pct: number;
    error_message: string | null;
    console_log_excerpt: string | null;
    started_at: string | null;
    completed_at: string | null;
    created_at: string | null;
  }

  interface LayerBuildDetail extends LayerBuild {
    vm_status?: string | null;
    vm_ip?: string | null;
    live_console?: string | null;
  }

  interface LayerConsume {
    id: number;
    profile_name: string;
    server_id: string | null;
    port_id: string | null;
    server_name: string | null;
    share_id: string;
    status: string;
    error_message: string | null;
    created_at: string | null;
    completed_at: string | null;
    vm_status?: string | null;
    vm_ip?: string | null;
  }

  // ---------------------------------------------------------------------------
  // 상태
  // ---------------------------------------------------------------------------

  const TERMINAL = new Set(['complete', 'error', 'timeout', 'cancelled']);

  const token = $derived($auth.token ?? undefined);
  const projectId = $derived($auth.projectId ?? undefined);

  let builds = $state<LayerBuild[]>([]);
  let consumes = $state<LayerConsume[]>([]);
  let loading = $state(true);
  let error = $state('');
  let message = $state('');

  const activeBuilds = $derived(builds.filter(b => !TERMINAL.has(b.status)));

  // ---------------------------------------------------------------------------
  // 빌드 폼
  // ---------------------------------------------------------------------------

  let buildForm = $state({
    layer_name: '',
    python_version: '3.11',
    pip_packages: '',
    profile_name: 'default',
  });
  let buildSubmitting = $state(false);

  // ---------------------------------------------------------------------------
  // 소비 폼
  // ---------------------------------------------------------------------------

  let consumeForm = $state({
    profile_name: 'default',
    server_name: '',
    flavor_id: '',
    image_id: '',
    network_id: '',
  });
  let consumeSubmitting = $state(false);

  // ---------------------------------------------------------------------------
  // 빌드 상세 모달
  // ---------------------------------------------------------------------------

  let detailOpen = $state(false);
  let selectedBuildId = $state<number | null>(null);
  let buildDetail = $state<LayerBuildDetail | null>(null);
  let detailLoading = $state(false);
  let detailCancelling = $state(false);
  let detailCancelError = $state('');

  const detailIsActive = $derived(buildDetail ? !TERMINAL.has(buildDetail.status) : false);

  // ---------------------------------------------------------------------------
  // 소비 상세 모달
  // ---------------------------------------------------------------------------

  let consumeDetailOpen = $state(false);
  let selectedConsumeId = $state<number | null>(null);
  let consumeDetail = $state<LayerConsume | null>(null);
  let consumeDetailLoading = $state(false);

  // ---------------------------------------------------------------------------
  // API 호출
  // ---------------------------------------------------------------------------

  async function loadBuilds() {
    try {
      builds = await api.get<LayerBuild[]>('/api/v1/admin/layers/builds', token, projectId, { refresh: true });
    } catch { /* 무시 */ }
  }

  async function loadConsumes() {
    try {
      consumes = await api.get<LayerConsume[]>('/api/v1/admin/layers/consumes', token, projectId, { refresh: true });
    } catch { /* 무시 */ }
  }

  async function loadAll() {
    if (builds.length === 0 && consumes.length === 0) loading = true;
    error = '';
    await Promise.allSettled([loadBuilds(), loadConsumes()]);
    loading = false;
  }

  // 활성 빌드가 있으면 10초, 없으면 30초 폴링
  $effect(() => {
    const interval = setInterval(loadBuilds, activeBuilds.length > 0 ? 10_000 : 30_000);
    return () => clearInterval(interval);
  });

  $effect(() => {
    if (!token) return;
    untrack(() => loadAll());
  });

  // ---------------------------------------------------------------------------
  // 빌드 트리거
  // ---------------------------------------------------------------------------

  async function triggerBuild() {
    if (buildSubmitting) return;
    buildSubmitting = true;
    error = '';
    message = '';
    try {
      const pip = buildForm.pip_packages
        .split(',')
        .map(s => s.trim())
        .filter(Boolean);
      const result = await api.post<{ build_id: number; layer_name: string; status: string }>(
        '/api/v1/admin/layers/build',
        {
          layer_name: buildForm.layer_name,
          python_version: buildForm.python_version,
          pip_packages: pip,
          profile_name: buildForm.profile_name,
        },
        token,
        projectId,
      );
      message = `레이어 빌드 시작 (ID: ${result.build_id}, 레이어: ${result.layer_name})`;
      await loadBuilds();
    } catch (e) {
      error = e instanceof ApiError ? `빌드 트리거 실패: ${e.message}` : '네트워크 오류';
    } finally {
      buildSubmitting = false;
    }
  }

  // ---------------------------------------------------------------------------
  // 소비 인스턴스 생성
  // ---------------------------------------------------------------------------

  async function triggerConsume() {
    if (consumeSubmitting) return;
    consumeSubmitting = true;
    error = '';
    message = '';
    try {
      const body: Record<string, string> = {
        profile_name: consumeForm.profile_name,
        server_name: consumeForm.server_name,
        flavor_id: consumeForm.flavor_id,
      };
      if (consumeForm.image_id) body.image_id = consumeForm.image_id;
      if (consumeForm.network_id) body.network_id = consumeForm.network_id;

      const result = await api.post<{ consume_id: number; server_id: string; status: string }>(
        '/api/v1/admin/layers/consume',
        body,
        token,
        projectId,
      );
      message = `소비 인스턴스 생성됨 (ID: ${result.consume_id}, 서버: ${result.server_id?.slice(0, 8)}…)`;
      await loadConsumes();
    } catch (e) {
      error = e instanceof ApiError ? `소비 인스턴스 생성 실패: ${e.message}` : '네트워크 오류';
    } finally {
      consumeSubmitting = false;
    }
  }

  // ---------------------------------------------------------------------------
  // 빌드 상세 모달
  // ---------------------------------------------------------------------------

  async function openBuildDetail(build: LayerBuild) {
    selectedBuildId = build.id;
    detailOpen = true;
    buildDetail = null;
    detailCancelError = '';
  }

  async function loadBuildDetail() {
    if (!selectedBuildId) return;
    detailLoading = true;
    try {
      buildDetail = await api.get<LayerBuildDetail>(
        `/api/v1/admin/layers/builds/${selectedBuildId}`,
        token,
        projectId,
        { refresh: true },
      );
    } catch { /* 이전 값 유지 */ } finally {
      detailLoading = false;
    }
  }

  async function cancelBuild() {
    if (!selectedBuildId || detailCancelling) return;
    detailCancelling = true;
    detailCancelError = '';
    try {
      await api.post(`/api/v1/admin/layers/builds/${selectedBuildId}/cancel`, {}, token, projectId);
      await Promise.allSettled([loadBuildDetail(), loadBuilds()]);
    } catch (e) {
      detailCancelError = e instanceof ApiError ? e.message : '취소 실패';
    } finally {
      detailCancelling = false;
    }
  }

  $effect(() => {
    if (detailOpen && selectedBuildId) {
      loadBuildDetail();
    } else {
      buildDetail = null;
    }
  });

  $effect(() => {
    if (!detailOpen || !selectedBuildId) return;
    const interval = setInterval(() => {
      if (detailIsActive) loadBuildDetail();
    }, 10_000);
    return () => clearInterval(interval);
  });

  // ---------------------------------------------------------------------------
  // 소비 상세 모달
  // ---------------------------------------------------------------------------

  async function openConsumeDetail(c: LayerConsume) {
    selectedConsumeId = c.id;
    consumeDetailOpen = true;
    consumeDetail = null;
  }

  async function loadConsumeDetail() {
    if (!selectedConsumeId) return;
    consumeDetailLoading = true;
    try {
      consumeDetail = await api.get<LayerConsume>(
        `/api/v1/admin/layers/consumes/${selectedConsumeId}`,
        token,
        projectId,
        { refresh: true },
      );
    } catch { /* 무시 */ } finally {
      consumeDetailLoading = false;
    }
  }

  $effect(() => {
    if (consumeDetailOpen && selectedConsumeId) {
      loadConsumeDetail();
    } else {
      consumeDetail = null;
    }
  });

  // ---------------------------------------------------------------------------
  // 유틸
  // ---------------------------------------------------------------------------

  function fmtRelative(iso: string | null | undefined): string {
    if (!iso) return '—';
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

  function fmtDate(iso: string | null | undefined): string {
    if (!iso) return '—';
    return new Date(iso).toLocaleString('ko-KR');
  }

  function elapsed(started: string | null | undefined): string {
    if (!started) return '—';
    const ms = Date.now() - new Date(started).getTime();
    const s = Math.floor(ms / 1000);
    if (s < 60) return `${s}초`;
    const m = Math.floor(s / 60);
    if (m < 60) return `${m}분 ${s % 60}초`;
    return `${Math.floor(m / 60)}시간 ${m % 60}분`;
  }
</script>

<div class="flex flex-col h-full overflow-auto bg-gray-900 text-gray-100 p-6">
  <PageHeader title="squashfs 레이어 관리" breadcrumb="레이어">
    {#snippet actions()}
      <button
        onclick={loadAll}
        class="text-xs text-gray-400 hover:text-white transition-colors px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600"
      >새로고침</button>
    {/snippet}
  </PageHeader>

  {#if error}
    <div class="mb-4 p-3 bg-red-900/40 border border-red-700 rounded-md text-red-300 text-sm">{error}</div>
  {/if}
  {#if message}
    <div class="mb-4 p-3 bg-green-900/40 border border-green-700 rounded-md text-green-300 text-sm">{message}</div>
  {/if}

  {#if loading}
    <LoadingSkeleton rows={4} />
  {:else}
    <div class="grid grid-cols-1 xl:grid-cols-2 gap-6 mb-8">
      <!-- ------------------------------------------------------------------ -->
      <!-- Button 1: 레이어 빌드                                               -->
      <!-- ------------------------------------------------------------------ -->
      <section class="bg-gray-800 border border-gray-700 rounded-xl p-5">
        <h2 class="text-sm font-semibold text-white mb-1">레이어 빌드</h2>
        <p class="text-xs text-gray-400 mb-4">
          squashfs Python 레이어를 빌드해 layer-store-rw NFS share에 저장합니다.
          빌드 VM이 자동으로 생성·실행·삭제됩니다.
        </p>

        <div class="space-y-3">
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs text-gray-400 mb-1" for="layer-name">레이어 이름 *</label>
              <input
                id="layer-name"
                type="text"
                placeholder="예: uvpy311"
                bind:value={buildForm.layer_name}
                class="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label class="block text-xs text-gray-400 mb-1" for="python-ver">Python 버전 *</label>
              <input
                id="python-ver"
                type="text"
                placeholder="3.11"
                bind:value={buildForm.python_version}
                class="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs text-gray-400 mb-1" for="profile-name">프로필 이름</label>
              <input
                id="profile-name"
                type="text"
                placeholder="default"
                bind:value={buildForm.profile_name}
                class="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label class="block text-xs text-gray-400 mb-1" for="pip-packages">pip 패키지 (쉼표 구분)</label>
              <input
                id="pip-packages"
                type="text"
                placeholder="numpy,pandas,scikit-learn"
                bind:value={buildForm.pip_packages}
                class="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          <button
            onclick={triggerBuild}
            disabled={buildSubmitting || !buildForm.layer_name || !buildForm.python_version}
            class="w-full py-2 px-4 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors"
          >
            {buildSubmitting ? '빌드 시작 중...' : '레이어 빌드 시작'}
          </button>
        </div>
      </section>

      <!-- ------------------------------------------------------------------ -->
      <!-- Button 2: 소비 인스턴스 생성                                        -->
      <!-- ------------------------------------------------------------------ -->
      <section class="bg-gray-800 border border-gray-700 rounded-xl p-5">
        <h2 class="text-sm font-semibold text-white mb-1">소비 인스턴스 생성</h2>
        <p class="text-xs text-gray-400 mb-4">
          layer-store-ro NFS share를 RO 마운트하고 layer-activate.sh로
          squashfs + OverlayFS를 활성화한 VM을 생성합니다.
        </p>

        <div class="space-y-3">
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs text-gray-400 mb-1" for="consume-profile">프로필 이름 *</label>
              <input
                id="consume-profile"
                type="text"
                placeholder="default"
                bind:value={consumeForm.profile_name}
                class="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label class="block text-xs text-gray-400 mb-1" for="server-name">서버 이름 *</label>
              <input
                id="server-name"
                type="text"
                placeholder="layer-consumer-01"
                bind:value={consumeForm.server_name}
                class="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          <div>
            <label class="block text-xs text-gray-400 mb-1" for="flavor-id">Flavor ID *</label>
            <input
              id="flavor-id"
              type="text"
              placeholder="flavor UUID 또는 이름"
              bind:value={consumeForm.flavor_id}
              class="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
            />
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs text-gray-400 mb-1" for="image-id">Image ID (선택)</label>
              <input
                id="image-id"
                type="text"
                placeholder="기본 이미지 사용"
                bind:value={consumeForm.image_id}
                class="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label class="block text-xs text-gray-400 mb-1" for="network-id">Network ID (선택)</label>
              <input
                id="network-id"
                type="text"
                placeholder="기본 네트워크 사용"
                bind:value={consumeForm.network_id}
                class="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          <button
            onclick={triggerConsume}
            disabled={consumeSubmitting || !consumeForm.profile_name || !consumeForm.server_name || !consumeForm.flavor_id}
            class="w-full py-2 px-4 bg-purple-600 hover:bg-purple-500 disabled:bg-gray-700 disabled:text-gray-500 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors"
          >
            {consumeSubmitting ? '인스턴스 생성 중...' : '소비 인스턴스 생성'}
          </button>
        </div>
      </section>
    </div>

    <!-- ---------------------------------------------------------------------- -->
    <!-- 빌드 현황 테이블                                                        -->
    <!-- ---------------------------------------------------------------------- -->
    <div class="mb-6">
      <h3 class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">
        빌드 현황
        {#if activeBuilds.length > 0}
          <span class="ml-2 text-blue-400 normal-case">(10초마다 자동 갱신)</span>
        {/if}
      </h3>
      {#if builds.length === 0}
        <div class="bg-gray-800 border border-gray-700 rounded-xl p-6 text-center text-gray-500 text-sm">
          빌드 기록이 없습니다
        </div>
      {:else}
        <div class="bg-gray-800 border border-gray-700 rounded-xl overflow-hidden">
          <div class="max-h-72 overflow-y-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="text-xs text-gray-500 uppercase tracking-wide sticky top-0 z-10 bg-gray-800 [box-shadow:inset_0_-1px_0_#374151]">
                  <th class="text-left px-4 py-2.5">레이어 이름</th>
                  <th class="text-left px-4 py-2.5 hidden sm:table-cell">Python</th>
                  <th class="text-left px-4 py-2.5">상태</th>
                  <th class="text-left px-4 py-2.5 hidden md:table-cell">단계</th>
                  <th class="text-left px-4 py-2.5 w-36 hidden lg:table-cell">진행률</th>
                  <th class="text-left px-4 py-2.5 hidden xl:table-cell">VM</th>
                  <th class="text-left px-4 py-2.5 hidden lg:table-cell">시작</th>
                  <th class="px-4 py-2.5"></th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-700/50">
                {#each builds as build (build.id)}
                  {@const isDone = TERMINAL.has(build.status)}
                  <tr
                    class="hover:bg-gray-700/30 transition-colors cursor-pointer {isDone ? 'opacity-50' : ''}"
                    onclick={() => openBuildDetail(build)}
                  >
                    <td class="px-4 py-2.5 font-medium text-white max-w-28 truncate">{build.layer_name}</td>
                    <td class="px-4 py-2.5 text-gray-400 text-xs font-mono hidden sm:table-cell">{build.python_version}</td>
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
    </div>

    <!-- ---------------------------------------------------------------------- -->
    <!-- 소비 인스턴스 테이블                                                    -->
    <!-- ---------------------------------------------------------------------- -->
    <div>
      <h3 class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">소비 인스턴스</h3>
      {#if consumes.length === 0}
        <div class="bg-gray-800 border border-gray-700 rounded-xl p-6 text-center text-gray-500 text-sm">
          생성된 소비 인스턴스가 없습니다
        </div>
      {:else}
        <div class="bg-gray-800 border border-gray-700 rounded-xl overflow-hidden">
          <div class="max-h-72 overflow-y-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="text-xs text-gray-500 uppercase tracking-wide sticky top-0 z-10 bg-gray-800 [box-shadow:inset_0_-1px_0_#374151]">
                  <th class="text-left px-4 py-2.5">서버 이름</th>
                  <th class="text-left px-4 py-2.5 hidden sm:table-cell">프로필</th>
                  <th class="text-left px-4 py-2.5">상태</th>
                  <th class="text-left px-4 py-2.5 hidden xl:table-cell">서버 ID</th>
                  <th class="text-left px-4 py-2.5 hidden lg:table-cell">생성</th>
                  <th class="px-4 py-2.5"></th>
                </tr>
              </thead>
              <tbody class="divide-y divide-gray-700/50">
                {#each consumes as c (c.id)}
                  <tr
                    class="hover:bg-gray-700/30 transition-colors cursor-pointer"
                    onclick={() => openConsumeDetail(c)}
                  >
                    <td class="px-4 py-2.5 font-medium text-white max-w-28 truncate">{c.server_name ?? '—'}</td>
                    <td class="px-4 py-2.5 text-gray-400 text-xs hidden sm:table-cell">{c.profile_name}</td>
                    <td class="px-4 py-2.5">
                      <StatusChip status={c.status} />
                    </td>
                    <td class="px-4 py-2.5 text-gray-500 text-xs font-mono hidden xl:table-cell">
                      {c.server_id ? c.server_id.slice(0, 8) + '…' : '—'}
                    </td>
                    <td class="px-4 py-2.5 text-gray-500 text-xs hidden lg:table-cell">
                      {fmtRelative(c.created_at)}
                    </td>
                    <td class="px-4 py-2.5 text-right">
                      <button
                        onclick={(e) => { e.stopPropagation(); openConsumeDetail(c); }}
                        class="text-xs text-purple-400 hover:text-purple-300 transition-colors"
                      >상세</button>
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        </div>
      {/if}
    </div>
  {/if}
</div>

<!-- -------------------------------------------------------------------------- -->
<!-- 빌드 상세 모달                                                              -->
<!-- -------------------------------------------------------------------------- -->
<Modal bind:open={detailOpen}>
  {#if detailOpen}
    <div class="bg-gray-900 rounded-xl border border-gray-700 w-full max-w-2xl mx-auto p-6 space-y-5">
      <div class="flex items-start justify-between gap-3">
        <div>
          <p class="text-xs text-gray-500 mb-1">레이어 빌드 상세</p>
          <h2 class="text-base font-semibold text-white">{buildDetail?.layer_name ?? '—'}</h2>
          <p class="text-xs text-gray-500 mt-0.5">Python {buildDetail?.python_version ?? '—'} · 프로필: {buildDetail?.profile_name ?? '—'}</p>
        </div>
        <div class="flex items-center gap-2 shrink-0">
          {#if buildDetail?.status}
            <StatusChip status={buildDetail.status} />
          {/if}
          <button
            onclick={() => (detailOpen = false)}
            class="text-gray-500 hover:text-white transition-colors ml-2"
            aria-label="닫기"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {#if detailLoading && !buildDetail}
        <div class="space-y-2">
          {#each [1, 2, 3] as _}
            <div class="h-8 bg-gray-800 rounded animate-pulse"></div>
          {/each}
        </div>
      {:else if buildDetail}
        <!-- 진행률 바 -->
        <div>
          <div class="flex justify-between text-xs text-gray-400 mb-1">
            <span>{buildDetail.progress_step || '대기 중'}</span>
            <span>{buildDetail.progress_pct}%</span>
          </div>
          <div class="h-1.5 bg-gray-700 rounded-full overflow-hidden">
            <div
              class="h-full rounded-full transition-all duration-500 {buildDetail.status === 'complete' ? 'bg-green-500' : buildDetail.status === 'error' || buildDetail.status === 'cancelled' ? 'bg-red-500' : 'bg-blue-500'}"
              style="width: {buildDetail.progress_pct}%"
            ></div>
          </div>
        </div>

        <!-- 정보 그리드 -->
        <div class="grid grid-cols-2 gap-3 text-xs">
          <div class="bg-gray-800/60 rounded-lg px-3 py-2.5">
            <p class="text-gray-500 mb-0.5">VM 인스턴스</p>
            <p class="text-white font-mono truncate">{buildDetail.server_id ? buildDetail.server_id.slice(0, 18) + '…' : '—'}</p>
          </div>
          <div class="bg-gray-800/60 rounded-lg px-3 py-2.5">
            <p class="text-gray-500 mb-0.5">VM 상태</p>
            {#if buildDetail.vm_status}
              <StatusChip status={buildDetail.vm_status.toLowerCase()} />
            {:else}
              <p class="text-gray-400">—</p>
            {/if}
          </div>
          <div class="bg-gray-800/60 rounded-lg px-3 py-2.5">
            <p class="text-gray-500 mb-0.5">VM IP</p>
            <p class="text-white font-mono">{buildDetail.vm_ip ?? '—'}</p>
          </div>
          <div class="bg-gray-800/60 rounded-lg px-3 py-2.5">
            <p class="text-gray-500 mb-0.5">경과 시간</p>
            <p class="text-white">{elapsed(buildDetail.started_at)}</p>
          </div>
          <div class="bg-gray-800/60 rounded-lg px-3 py-2.5">
            <p class="text-gray-500 mb-0.5">시작 시각</p>
            <p class="text-white">{fmtDate(buildDetail.started_at)}</p>
          </div>
          <div class="bg-gray-800/60 rounded-lg px-3 py-2.5">
            <p class="text-gray-500 mb-0.5">완료 시각</p>
            <p class="text-white">{fmtDate(buildDetail.completed_at)}</p>
          </div>
          {#if buildDetail.share_id}
            <div class="col-span-2 bg-gray-800/60 rounded-lg px-3 py-2.5">
              <p class="text-gray-500 mb-0.5">NFS Share ID</p>
              <p class="text-white font-mono text-[11px] truncate">{buildDetail.share_id}</p>
            </div>
          {/if}
        </div>

        {#if buildDetail.error_message}
          <div class="bg-red-900/30 border border-red-700/50 rounded-lg px-3 py-2.5">
            <p class="text-xs text-red-400 font-medium mb-1">오류</p>
            <p class="text-xs text-red-300 font-mono whitespace-pre-wrap break-all">{buildDetail.error_message}</p>
          </div>
        {/if}

        <!-- 콘솔 로그 -->
        <div>
          <div class="flex items-center justify-between mb-1.5">
            <p class="text-xs text-gray-500">
              {#if buildDetail.live_console}
                콘솔 로그 {detailIsActive ? '(10초마다 자동 갱신)' : ''}
              {:else if buildDetail.console_log_excerpt}
                마지막 저장 로그
              {:else}
                콘솔 로그
              {/if}
            </p>
            {#if detailIsActive}
              <button
                onclick={loadBuildDetail}
                class="text-[11px] text-blue-400 hover:text-blue-300 transition-colors"
              >새로고침</button>
            {/if}
          </div>
          {#if buildDetail.live_console || buildDetail.console_log_excerpt}
            <pre class="bg-gray-950 text-[11px] text-gray-300 font-mono whitespace-pre-wrap break-all overflow-auto max-h-56 rounded-lg p-3 border border-gray-800">{buildDetail.live_console || buildDetail.console_log_excerpt}</pre>
          {:else}
            <div class="bg-gray-950 rounded-lg p-3 border border-gray-800 text-[11px] text-gray-500 font-mono">
              로그 없음
            </div>
          {/if}
        </div>

        <!-- 하단 액션 -->
        <div class="flex items-center justify-between pt-1 border-t border-gray-800">
          {#if detailCancelError}
            <p class="text-xs text-red-400">{detailCancelError}</p>
          {:else}
            <div></div>
          {/if}
          <div class="flex gap-2">
            {#if detailIsActive}
              <button
                onclick={cancelBuild}
                disabled={detailCancelling}
                class="px-3 py-1.5 text-xs text-red-400 border border-red-700/50 hover:bg-red-900/30 disabled:opacity-50 rounded-lg transition-colors"
              >
                {detailCancelling ? '취소 중...' : '빌드 취소'}
              </button>
            {/if}
            <button
              onclick={() => (detailOpen = false)}
              class="px-3 py-1.5 text-xs text-gray-400 border border-gray-700 hover:bg-gray-800 rounded-lg transition-colors"
            >닫기</button>
          </div>
        </div>
      {/if}
    </div>
  {/if}
</Modal>

<!-- -------------------------------------------------------------------------- -->
<!-- 소비 상세 모달                                                              -->
<!-- -------------------------------------------------------------------------- -->
<Modal bind:open={consumeDetailOpen}>
  {#if consumeDetailOpen}
    <div class="bg-gray-900 rounded-xl border border-gray-700 w-full max-w-xl mx-auto p-6 space-y-4">
      <div class="flex items-start justify-between gap-3">
        <div>
          <p class="text-xs text-gray-500 mb-1">소비 인스턴스 상세</p>
          <h2 class="text-base font-semibold text-white">{consumeDetail?.server_name ?? '—'}</h2>
          <p class="text-xs text-gray-500 mt-0.5">프로필: {consumeDetail?.profile_name ?? '—'}</p>
        </div>
        <div class="flex items-center gap-2 shrink-0">
          {#if consumeDetail?.status}
            <StatusChip status={consumeDetail.status} />
          {/if}
          <button
            onclick={() => (consumeDetailOpen = false)}
            class="text-gray-500 hover:text-white transition-colors ml-2"
            aria-label="닫기"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {#if consumeDetailLoading && !consumeDetail}
        <div class="space-y-2">
          {#each [1, 2, 3] as _}
            <div class="h-8 bg-gray-800 rounded animate-pulse"></div>
          {/each}
        </div>
      {:else if consumeDetail}
        <div class="grid grid-cols-2 gap-3 text-xs">
          <div class="bg-gray-800/60 rounded-lg px-3 py-2.5">
            <p class="text-gray-500 mb-0.5">서버 ID</p>
            <p class="text-white font-mono truncate">{consumeDetail.server_id ? consumeDetail.server_id.slice(0, 18) + '…' : '—'}</p>
          </div>
          <div class="bg-gray-800/60 rounded-lg px-3 py-2.5">
            <p class="text-gray-500 mb-0.5">VM 상태</p>
            {#if consumeDetail.vm_status}
              <StatusChip status={consumeDetail.vm_status.toLowerCase()} />
            {:else}
              <p class="text-gray-400">—</p>
            {/if}
          </div>
          <div class="bg-gray-800/60 rounded-lg px-3 py-2.5">
            <p class="text-gray-500 mb-0.5">VM IP</p>
            <p class="text-white font-mono">{consumeDetail.vm_ip ?? '—'}</p>
          </div>
          <div class="bg-gray-800/60 rounded-lg px-3 py-2.5">
            <p class="text-gray-500 mb-0.5">생성 시각</p>
            <p class="text-white">{fmtDate(consumeDetail.created_at)}</p>
          </div>
          {#if consumeDetail.share_id}
            <div class="col-span-2 bg-gray-800/60 rounded-lg px-3 py-2.5">
              <p class="text-gray-500 mb-0.5">NFS Share ID (RO)</p>
              <p class="text-white font-mono text-[11px] truncate">{consumeDetail.share_id}</p>
            </div>
          {/if}
        </div>

        {#if consumeDetail.error_message}
          <div class="bg-red-900/30 border border-red-700/50 rounded-lg px-3 py-2.5">
            <p class="text-xs text-red-400 font-medium mb-1">오류</p>
            <p class="text-xs text-red-300 font-mono whitespace-pre-wrap break-all">{consumeDetail.error_message}</p>
          </div>
        {/if}

        <div class="flex justify-end pt-1 border-t border-gray-800">
          <button
            onclick={() => (consumeDetailOpen = false)}
            class="px-3 py-1.5 text-xs text-gray-400 border border-gray-700 hover:bg-gray-800 rounded-lg transition-colors"
          >닫기</button>
        </div>
      {/if}
    </div>
  {/if}
</Modal>
