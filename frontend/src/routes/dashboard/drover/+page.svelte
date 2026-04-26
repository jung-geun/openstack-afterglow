<script lang="ts">
  import { untrack } from 'svelte';
  import { auth } from '$lib/stores/auth';
  import { api, ApiError, getBaseUrl } from '$lib/api/client';
  import { toast } from '$lib/stores/toast';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
  import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
  import K3sClusterDetailPanel from '$lib/components/K3sClusterDetailPanel.svelte';
  import SlidePanel from '$lib/components/SlidePanel.svelte';
  import StatusChip from '$lib/components/ui/StatusChip.svelte';
  import PageHeader from '$lib/components/ui/PageHeader.svelte';
  import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';

  interface K3sCluster {
    id: string;
    name: string;
    status: string;
    status_reason: string | null;
    server_vm_id: string | null;
    agent_vm_ids: string[];
    agent_count: number;
    api_address: string | null;
    server_ip: string | null;
    network_id: string | null;
    key_name: string | null;
    k3s_version: string | null;
    created_at: string | null;
    updated_at: string | null;
    deleted_at: string | null;
    deleted_by_user_id: string | null;
    deleted_reason: string | null;
  }

  interface Flavor {
    id: string;
    name: string;
    vcpus: number;
    ram: number;
    disk: number;
  }

  interface Network {
    id: string;
    name: string;
    is_external: boolean;
  }

  interface Keypair {
    name: string;
  }


  const K3S_BASE_STEPS = [
    { id: 'security_group',   label: '보안 그룹' },
    { id: 'server_volume',    label: '서버 볼륨' },
    { id: 'server_creating',  label: '서버 VM' },
    { id: 'waiting_callback', label: 'k3s 초기화' },
    { id: 'completed',        label: '완료' },
  ];

  const K3S_LB_STEP = { id: 'lb_creating', label: '로드밸런서' };

  // api_lb_enabled이면 LB 스텝 포함, 또는 SSE에서 lb_creating 이벤트 수신 시 동적 추가
  let k3sSteps = $derived.by(() => {
    const hasLb = form.api_lb_enabled || progressStep === 'lb_creating';
    if (hasLb) {
      const steps = [...K3S_BASE_STEPS];
      steps.splice(1, 0, K3S_LB_STEP); // 보안 그룹 다음에 삽입
      return steps;
    }
    return K3S_BASE_STEPS;
  });

  // 슬라이드 패널
  let selectedClusterId = $state<string | null>(null);

  function openClusterPanel(id: string) {
    selectedClusterId = id;
    history.pushState({ clusterId: id }, '', `/dashboard/drover/${id}`);
  }

  function closeClusterPanel() {
    selectedClusterId = null;
    history.pushState({}, '', '/dashboard/drover');
  }

  $effect(() => {
    function handlePopState(e: PopStateEvent) {
      if (e.state?.clusterId) {
        selectedClusterId = e.state.clusterId;
      } else {
        selectedClusterId = null;
      }
    }
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  });

  let clusters = $state<K3sCluster[]>([]);
  let flavors = $state<Flavor[]>([]);
  let networks = $state<Network[]>([]);
  let keypairs = $state<Keypair[]>([]);
  let loading = $state(true);
  let refreshing = $state(false);
  let error = $state('');
  let deleting = $state<string | null>(null);
  let showDeleted = $state(false);

  // 모달
  let showModal = $state(false);
  let creating = $state(false);
  let createError = $state('');
  let form = $state({ name: '', agent_count: 1, agent_flavor_id: '', network_id: '', key_name: '', api_lb_enabled: false, api_lb_network_id: '', os_type: 'ubuntu' });

  // SSE 진행률
  let showProgress = $state(false);
  let progressStep = $state('');
  let progressPct = $state(0);
  let progressMsg = $state('');
  let progressError = $state('');
  let createdClusterId = $state<string | null>(null);
  let elapsedSeconds = $state(0);
  let stepTimings = $state<Record<string, number>>({});
  let lastStepSeen = $state('');

  const token = $derived($auth.token ?? undefined);
  const projectId = $derived($auth.projectId ?? undefined);

  async function fetchClusters(opts?: { refresh?: boolean }) {
    try {
      const qs = showDeleted ? '?include_deleted=true' : '';
      clusters = await api.get<K3sCluster[]>(`/api/k3s/clusters${qs}`, token, projectId, opts);
      error = '';
    } catch (e) {
      if (e instanceof ApiError && e.status === 503) {
        error = 'k3s 서비스를 사용할 수 없습니다.';
      } else {
        error = e instanceof ApiError ? `조회 실패 (${e.status})` : '서버 오류';
      }
    } finally {
      loading = false;
    }
  }

  async function openCreateModal() {
    showModal = true;
    form = { name: '', agent_count: 1, agent_flavor_id: '', network_id: '', key_name: '', api_lb_enabled: false, api_lb_network_id: '', os_type: 'ubuntu' };
    createError = '';
    try {
      [flavors, networks, keypairs] = await Promise.all([
        api.get<Flavor[]>('/api/flavors', token, projectId),
        api.get<Network[]>('/api/networks', token, projectId),
        api.get<Keypair[]>('/api/keypairs', token, projectId),
      ]);
      // 기본 tenant 네트워크(Default) 자동 선택
      const defaultNet = networks.find(n => !n.is_external && (n.name === 'Default' || n.name === 'default'));
      if (defaultNet) form.network_id = defaultNet.id;
    } catch {
      flavors = []; networks = []; keypairs = [];
    }
  }

  async function createCluster() {
    creating = true;
    createError = '';
    showModal = false;
    showProgress = true;
    progressStep = '';
    progressPct = 0;
    progressMsg = '클러스터 생성 준비 중...';
    progressError = '';
    createdClusterId = null;
    elapsedSeconds = 0;
    stepTimings = {};
    lastStepSeen = '';

    try {
      const baseUrl = getBaseUrl();

      const res = await fetch(`${baseUrl}/api/k3s/clusters/async`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
          ...(token ? { 'X-Auth-Token': token } : {}),
          ...(projectId ? { 'X-Project-Id': projectId } : {}),
        },
        body: JSON.stringify({
          name: form.name,
          agent_count: form.agent_count,
          os_type: form.os_type,
          ...(form.agent_flavor_id ? { agent_flavor_id: form.agent_flavor_id } : {}),
          ...(form.network_id ? { network_id: form.network_id } : {}),
          ...(form.key_name ? { key_name: form.key_name } : {}),
          api_lb_enabled: form.api_lb_enabled,
          ...(form.api_lb_network_id ? { api_lb_network_id: form.api_lb_network_id } : {}),
        }),
      });

      if (!res.ok || !res.body) {
        const text = await res.text().catch(() => '');
        throw new Error(`HTTP ${res.status}: ${text}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop() ?? '';
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const msg = JSON.parse(line.slice(6));
            progressStep = msg.step;
            progressPct = msg.progress;
            progressMsg = msg.message;
            if (msg.elapsed_seconds != null) elapsedSeconds = msg.elapsed_seconds;
            if (msg.step !== lastStepSeen) {
              stepTimings[msg.step] = msg.elapsed_seconds ?? elapsedSeconds;
              lastStepSeen = msg.step;
            }
            if (msg.cluster_id) createdClusterId = msg.cluster_id;
            if (msg.step === 'completed') {
              toast.success(`클러스터 "${form.name || '클러스터'}" 생성 완료 (${elapsedSeconds}초)`);
            } else if (msg.step === 'failed') {
              progressError = msg.error || '알 수 없는 오류';
              toast.error(`클러스터 생성 실패: ${msg.error || '알 수 없는 오류'}`);
            }
          } catch {}
        }
      }
    } catch (e) {
      progressError = String(e);
      progressStep = 'failed';
    } finally {
      creating = false;
      await fetchClusters();
    }
  }

  async function deleteCluster(id: string, name: string) {
    if (!confirm(`Drover 클러스터 "${name}"을 삭제하시겠습니까?\n모든 VM과 보안 그룹이 삭제됩니다.`)) return;
    deleting = id;
    try {
      await api.delete(`/api/k3s/clusters/${id}`, token, projectId);
      await fetchClusters();
    } catch (e) {
      alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
    } finally {
      deleting = null;
    }
  }

  async function downloadKubeconfig(id: string, name: string) {
    const baseUrl = getBaseUrl();
    const res = await fetch(`${baseUrl}/api/k3s/clusters/${id}/kubeconfig`, {
      headers: {
        ...(token ? { 'X-Auth-Token': token } : {}),
        ...(projectId ? { 'X-Project-Id': projectId } : {}),
      },
    });
    if (!res.ok) {
      if (res.status === 404) {
        alert('kubeconfig가 아직 준비되지 않았습니다. 클러스터가 초기화 중입니다.');
      } else {
        alert(`다운로드 실패: HTTP ${res.status}`);
      }
      return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `kubeconfig-${name}.yaml`;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function forceRefresh() {
    refreshing = true;
    try {
      await fetchClusters({ refresh: true });
    } finally {
      refreshing = false;
    }
  }

  const ar = createAutoRefresh(() => fetchClusters(), {
    storageKey: 'dashboard-drover',
    defaultActive: true,
    defaultInterval: 10,
    intervalOptions: [10, 15, 30, 60],
  });

  $effect(() => {
    if (!$auth.projectId) return;
    loading = true;
    untrack(() => fetchClusters());
  });
</script>

<!-- 생성 모달 -->
{#if showModal}
  <div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
    onclick={() => { showModal = false; }}
    role="dialog" aria-modal="true" tabindex="-1"
    onkeydown={(e) => e.key === 'Escape' && (showModal = false)}>
    <div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-lg mx-4 shadow-2xl"
      onclick={(e) => e.stopPropagation()} role="none" onkeydown={(e) => e.stopPropagation()}>
      <h2 class="text-lg font-semibold text-white mb-5">Drover 클러스터 생성</h2>
      <div class="space-y-4">
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">클러스터 이름
            <input bind:value={form.name} type="text" placeholder="미입력 시 자동 생성"
              class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
          </label>
        </div>
        <div>
          <span class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">OS 타입</span>
          <div class="flex gap-2 mt-1.5">
            <button type="button"
              onclick={() => form.os_type = 'ubuntu'}
              class="flex-1 flex items-center gap-2 px-3 py-2.5 rounded-lg border text-sm transition-colors {form.os_type === 'ubuntu' ? 'border-blue-500 bg-blue-900/30 text-white' : 'border-gray-600 bg-gray-800 text-gray-400 hover:border-gray-500'}">
              <span class="text-base">🐧</span>
              <div class="text-left">
                <div class="font-medium leading-none">Ubuntu</div>
                <div class="text-xs text-gray-500 mt-0.5">cloud-init</div>
              </div>
            </button>
            <button type="button"
              onclick={() => form.os_type = 'fcos'}
              class="flex-1 flex items-center gap-2 px-3 py-2.5 rounded-lg border text-sm transition-colors {form.os_type === 'fcos' ? 'border-orange-500 bg-orange-900/30 text-white' : 'border-gray-600 bg-gray-800 text-gray-400 hover:border-gray-500'}">
              <span class="text-base">🔴</span>
              <div class="text-left">
                <div class="font-medium leading-none">CoreOS</div>
                <div class="text-xs text-gray-500 mt-0.5">Ignition</div>
              </div>
            </button>
          </div>
          {#if form.os_type === 'fcos'}
            <div class="mt-2 text-xs text-orange-400/80 bg-orange-900/10 border border-orange-800/40 rounded px-2.5 py-1.5">
              서버의 <code class="font-mono">k3s.fcos_image_id</code> 설정이 필요합니다.
            </div>
          {/if}
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">에이전트 수 (0-10)
            <input bind:value={form.agent_count} type="number" min="0" max="10"
              class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
          </label>
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">에이전트 플레이버 (선택)
            <select bind:value={form.agent_flavor_id}
              class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5">
              <option value="">기본값 사용</option>
              {#each flavors as f}
                <option value={f.id}>{f.name} ({f.vcpus}vCPU / {Math.round(f.ram/1024)}GB)</option>
              {/each}
            </select>
          </label>
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">네트워크 (선택)
            <select bind:value={form.network_id}
              class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5">
              <option value="">기본값 사용</option>
              {#each networks.filter(n => !n.is_external) as n}
                <option value={n.id}>{n.name || n.id.slice(0,12)}</option>
              {/each}
            </select>
          </label>
        </div>
        <div class="border border-gray-700 rounded-lg p-3">
          <label class="flex items-center gap-3 cursor-pointer">
            <div class="relative">
              <input type="checkbox" bind:checked={form.api_lb_enabled} class="sr-only" />
              <div class="w-9 h-5 rounded-full transition-colors {form.api_lb_enabled ? 'bg-blue-600' : 'bg-gray-600'}"></div>
              <div class="absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform {form.api_lb_enabled ? 'translate-x-4' : ''}"></div>
            </div>
            <span class="text-sm text-gray-300">외부 로드밸런서 사용</span>
          </label>
          <div class="text-xs text-gray-500 mt-1 ml-12">API 서버(6443)에 Octavia LB + Floating IP 연결</div>
          {#if form.api_lb_enabled}
            <div class="mt-3">
              <div class="text-xs text-gray-400 mb-1">LB Floating IP 네트워크</div>
              <select bind:value={form.api_lb_network_id}
                class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500">
                <option value="">서버 기본값 사용</option>
                {#each networks.filter(n => n.is_external) as n}
                  <option value={n.id}>{n.name || n.id.slice(0,12)}</option>
                {/each}
              </select>
            </div>
          {/if}
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">키페어 (선택)
            <select bind:value={form.key_name}
              class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5">
              <option value="">없음</option>
              {#each keypairs as kp}
                <option value={kp.name}>{kp.name}</option>
              {/each}
            </select>
          </label>
        </div>
      </div>
      {#if createError}
        <div class="mt-4 text-red-400 text-xs bg-red-900/20 border border-red-800 rounded px-3 py-2">{createError}</div>
      {/if}
      <div class="flex justify-end gap-3 mt-6">
        <button onclick={() => showModal = false}
          class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">취소</button>
        <button onclick={createCluster} disabled={creating}
          class="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors">
          생성
        </button>
      </div>
    </div>
  </div>
{/if}

<!-- SSE 진행률 -->
{#if showProgress}
  <div class="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
    <div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl">
      <h2 class="text-lg font-semibold text-white mb-4">Drover 클러스터 생성</h2>
      <!-- 스텝 표시 -->
      <div class="space-y-2 mb-4">
        {#each k3sSteps as step}
          {@const isCurrent = progressStep === step.id}
          {@const isDone = k3sSteps.findIndex(s => s.id === progressStep) > k3sSteps.findIndex(s => s.id === step.id)}
          {@const stepTime = stepTimings[step.id]}
          <div class="flex items-center gap-2 text-sm {isDone ? 'text-green-400' : isCurrent ? 'text-blue-400' : 'text-gray-600'}">
            <span class="w-4 h-4 flex items-center justify-center flex-shrink-0">
              {#if isDone}✓{:else if isCurrent}<span class="animate-pulse">●</span>{:else}○{/if}
            </span>
            <span class="flex-1">{step.label}</span>
            {#if isDone && stepTime != null}
              <span class="text-xs opacity-60">{stepTime}s~</span>
            {:else if isCurrent && elapsedSeconds > 0}
              <span class="text-xs opacity-60">{elapsedSeconds}s</span>
            {/if}
          </div>
        {/each}
      </div>
      <!-- 진행 바 -->
      <div class="bg-gray-800 rounded-full h-2 mb-3">
        <div class="bg-blue-500 h-2 rounded-full transition-all duration-500" style="width: {progressPct}%"></div>
      </div>
      <div class="flex items-center justify-between mb-4">
        <p class="text-sm text-gray-400">{progressMsg}</p>
        {#if elapsedSeconds > 0}
          <span class="text-xs text-gray-600 flex-shrink-0 ml-2">경과 {elapsedSeconds}초</span>
        {/if}
      </div>
      {#if progressError}
        <div class="text-red-400 text-xs bg-red-900/20 border border-red-800 rounded px-3 py-2 mb-4">{progressError}</div>
      {/if}
      {#if progressStep === 'completed' || progressStep === 'failed'}
        <div class="flex justify-end gap-3">
          <button onclick={() => { showProgress = false; }}
            class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">닫기</button>
          {#if createdClusterId && progressStep === 'completed'}
            <button
              onclick={() => { showProgress = false; openClusterPanel(createdClusterId!); }}
              class="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-colors">
              클러스터 보기
            </button>
          {/if}
        </div>
      {:else}
        <p class="text-xs text-gray-600">완료될 때까지 기다려주세요...</p>
      {/if}
    </div>
  </div>
{/if}

<!-- 슬라이드 패널 -->
{#if selectedClusterId}
  <SlidePanel onClose={closeClusterPanel}>
    <K3sClusterDetailPanel clusterId={selectedClusterId} onClose={closeClusterPanel} />
  </SlidePanel>
{/if}

<div class="p-4 md:p-8">
  <PageHeader breadcrumb="CONTAINERS / K3S" title="Drover 클러스터">
    {#snippet actions()}
      <button
        onclick={() => { showDeleted = !showDeleted; fetchClusters(); }}
        class="hidden sm:inline-flex text-xs px-3 py-1.5 rounded border transition-colors {showDeleted ? 'border-gray-500 text-gray-300 bg-gray-800' : 'border-gray-700 text-gray-500 hover:border-gray-500 hover:text-gray-400'}"
      >
        {showDeleted ? '삭제 이력 숨기기' : '삭제 이력 보기'}
      </button>
      <AutoRefreshControl
        bind:active={ar.active}
        bind:intervalSeconds={ar.intervalSeconds}
        intervalOptions={ar.intervalOptions}
        refreshing={refreshing || loading}
        onManualRefresh={forceRefresh}
      />
      <button onclick={openCreateModal}
        class="bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
        + 클러스터 생성
      </button>
    {/snippet}
  </PageHeader>

  <p class="text-sm text-gray-500 mb-6">Nova VM + cloud-init으로 k3s Kubernetes 클러스터를 프로비저닝합니다.</p>

  {#if error}
    <div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>
  {/if}

  {#if loading}
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
      {#each Array(3) as _}
        <div class="animate-pulse h-48 bg-gray-900 border border-gray-800 rounded-2xl"></div>
      {/each}
    </div>
  {:else if clusters.length === 0}
    <div class="text-center py-20 text-gray-600">
      <div class="text-5xl mb-4">☸</div>
      <p class="text-lg">Drover 클러스터가 없습니다</p>
      <button onclick={openCreateModal} class="text-blue-400 hover:text-blue-300 text-sm mt-2 inline-block">
        첫 클러스터를 생성하세요 →
      </button>
    </div>
  {:else}
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
      {#each clusters as cluster (cluster.id)}
        <div
          class="bg-gray-900 border border-gray-800 rounded-2xl p-5 transition-colors {cluster.deleted_at ? 'opacity-50' : 'cursor-pointer hover:border-gray-600'}"
          onclick={() => !cluster.deleted_at && openClusterPanel(cluster.id)}
          role={cluster.deleted_at ? undefined : 'button'}
          tabindex={cluster.deleted_at ? undefined : 0}
          onkeydown={(e) => e.key === 'Enter' && !cluster.deleted_at && openClusterPanel(cluster.id)}
        >
          <!-- Header -->
          <div class="flex items-center gap-2.5 mb-3">
            <div class="w-[34px] h-[34px] rounded-[9px] bg-emerald-500/12 border border-emerald-500/30 text-emerald-400 flex items-center justify-center shrink-0">
              <svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
              </svg>
            </div>
            <div class="flex-1 min-w-0">
              <div class="text-white font-semibold text-sm truncate {cluster.deleted_at ? 'line-through text-gray-500' : ''}">
                {cluster.name}
              </div>
              <div class="text-[11px] text-gray-500 font-mono mt-0.5">
                {cluster.k3s_version || 'k3s'}
              </div>
            </div>
            <StatusChip status={cluster.status} />
          </div>

          <!-- Info grid -->
          <div class="grid grid-cols-2 gap-2 text-xs mb-3.5">
            <div>
              <div class="text-[11px] uppercase tracking-wider font-medium text-gray-500">노드 (M+A)</div>
              <div class="text-gray-200 mt-0.5">{cluster.agent_count + 1} (1+{cluster.agent_count})</div>
            </div>
            <div>
              <div class="text-[11px] uppercase tracking-wider font-medium text-gray-500">API</div>
              <div class="text-gray-200 mt-0.5 font-mono text-xs truncate">{cluster.api_address || '—'}</div>
            </div>
            {#if cluster.deleted_at}
              <div class="col-span-2">
                <div class="text-[11px] uppercase tracking-wider font-medium text-gray-500">삭제됨</div>
                <div class="text-gray-500 mt-0.5 text-xs">{cluster.deleted_at.replace('T', ' ').slice(0, 16)}</div>
              </div>
            {:else if cluster.status_reason}
              <div class="col-span-2">
                <div class="text-[11px] text-gray-500 truncate">{cluster.status_reason}</div>
              </div>
            {/if}
          </div>

          <!-- Actions -->
          <div class="flex gap-1.5" role="none" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
            <button
              onclick={() => downloadKubeconfig(cluster.id, cluster.name)}
              disabled={cluster.status !== 'ACTIVE'}
              class="flex-1 text-blue-400 hover:text-blue-300 disabled:text-gray-600 text-xs px-2 py-1.5 rounded border border-blue-900 hover:border-blue-700 disabled:border-gray-700 transition-colors text-center"
            >kubeconfig</button>
            <button
              onclick={() => openClusterPanel(cluster.id)}
              disabled={!!cluster.deleted_at}
              class="text-gray-400 hover:text-white disabled:text-gray-600 text-xs px-2 py-1.5 rounded border border-gray-700 hover:border-gray-500 disabled:border-gray-700 transition-colors"
            >상세</button>
            {#if !cluster.deleted_at}
              <button
                onclick={() => deleteCluster(cluster.id, cluster.name)}
                disabled={deleting === cluster.id || cluster.status === 'DELETING'}
                class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-1.5 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors"
              >{deleting === cluster.id ? '삭제 중...' : '삭제'}</button>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>
