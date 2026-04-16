<script lang="ts">
  import { auth } from '$lib/stores/auth';
  import { untrack } from 'svelte';
  import { api, ApiError, getBaseUrl } from '$lib/api/client';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
  import RefreshButton from '$lib/components/RefreshButton.svelte';
  import AutoRefreshToggle from '$lib/components/AutoRefreshToggle.svelte';
  import K3sClusterDetailPanel from '$lib/components/K3sClusterDetailPanel.svelte';

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
  }

  interface Keypair {
    name: string;
  }

  const statusColor: Record<string, string> = {
    ACTIVE:       'text-green-400 bg-green-900/30',
    CREATING:     'text-yellow-400 bg-yellow-900/30',
    PROVISIONING: 'text-blue-400 bg-blue-900/30',
    DELETING:     'text-orange-400 bg-orange-900/30',
    ERROR:        'text-red-400 bg-red-900/30',
    DELETED:      'text-gray-500 bg-gray-800/50',
  };

  const K3S_STEPS = [
    { id: 'security_group',   label: '보안 그룹' },
    { id: 'server_volume',    label: '서버 볼륨' },
    { id: 'server_creating',  label: '서버 VM' },
    { id: 'waiting_callback', label: 'k3s 초기화' },
    { id: 'completed',        label: '완료' },
  ];

  // 슬라이드 패널
  let selectedClusterId = $state<string | null>(null);

  function openClusterPanel(id: string) {
    selectedClusterId = id;
    history.pushState({ clusterId: id }, '', `/dashboard/containers/k3s/${id}`);
  }

  function closeClusterPanel() {
    selectedClusterId = null;
    history.pushState({}, '', '/dashboard/containers/k3s');
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
  let autoRefresh = $state(false);
  let deleting = $state<string | null>(null);
  let showDeleted = $state(false);

  // 모달
  let showModal = $state(false);
  let creating = $state(false);
  let createError = $state('');
  let form = $state({ name: '', agent_count: 1, agent_flavor_id: '', network_id: '', key_name: '' });

  // SSE 진행률
  let showProgress = $state(false);
  let progressStep = $state('');
  let progressPct = $state(0);
  let progressMsg = $state('');
  let progressError = $state('');
  let createdClusterId = $state<string | null>(null);

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
    form = { name: '', agent_count: 1, agent_flavor_id: '', network_id: '', key_name: '' };
    createError = '';
    try {
      [flavors, networks, keypairs] = await Promise.all([
        api.get<Flavor[]>('/api/flavors', token, projectId),
        api.get<Network[]>('/api/networks', token, projectId),
        api.get<Keypair[]>('/api/keypairs', token, projectId),
      ]);
    } catch {
      flavors = []; networks = []; keypairs = [];
    }
  }

  async function createCluster() {
    if (!form.name.trim()) return;
    creating = true;
    createError = '';
    showModal = false;
    showProgress = true;
    progressStep = '';
    progressPct = 0;
    progressMsg = '클러스터 생성 준비 중...';
    progressError = '';
    createdClusterId = null;

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
          ...(form.agent_flavor_id ? { agent_flavor_id: form.agent_flavor_id } : {}),
          ...(form.network_id ? { network_id: form.network_id } : {}),
          ...(form.key_name ? { key_name: form.key_name } : {}),
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
            if (msg.cluster_id) createdClusterId = msg.cluster_id;
            if (msg.step === 'failed') {
              progressError = msg.error || '알 수 없는 오류';
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
    if (!confirm(`k3s 클러스터 "${name}"을 삭제하시겠습니까?\n모든 VM과 보안 그룹이 삭제됩니다.`)) return;
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

  $effect(() => {
    if (!$auth.projectId) return;
    loading = true;
    untrack(() => fetchClusters());
  });

  $effect(() => {
    if (!$auth.projectId || !autoRefresh) return;
    const interval = setInterval(() => untrack(() => fetchClusters()), 5000);
    return () => clearInterval(interval);
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
      <h2 class="text-lg font-semibold text-white mb-5">k3s 클러스터 생성</h2>
      <div class="space-y-4">
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">클러스터 이름 *
            <input bind:value={form.name} type="text" placeholder="my-cluster"
              class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
          </label>
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
              {#each networks as n}
                <option value={n.id}>{n.name || n.id.slice(0,12)}</option>
              {/each}
            </select>
          </label>
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
        <button onclick={createCluster} disabled={creating || !form.name.trim()}
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
      <h2 class="text-lg font-semibold text-white mb-4">k3s 클러스터 생성</h2>
      <!-- 스텝 표시 -->
      <div class="space-y-2 mb-4">
        {#each K3S_STEPS as step}
          {@const isCurrent = progressStep === step.id}
          {@const isDone = K3S_STEPS.findIndex(s => s.id === progressStep) > K3S_STEPS.findIndex(s => s.id === step.id)}
          <div class="flex items-center gap-2 text-sm {isDone ? 'text-green-400' : isCurrent ? 'text-blue-400' : 'text-gray-600'}">
            <span class="w-4 h-4 flex items-center justify-center">
              {#if isDone}✓{:else if isCurrent}<span class="animate-pulse">●</span>{:else}○{/if}
            </span>
            {step.label}
          </div>
        {/each}
      </div>
      <!-- 진행 바 -->
      <div class="bg-gray-800 rounded-full h-2 mb-3">
        <div class="bg-blue-500 h-2 rounded-full transition-all duration-500" style="width: {progressPct}%"></div>
      </div>
      <p class="text-sm text-gray-400 mb-4">{progressMsg}</p>
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
  <div
    class="fixed inset-0 z-40"
    role="dialog"
    aria-modal="true"
    onkeydown={(e) => e.key === 'Escape' && closeClusterPanel()}>
    <button
      class="absolute inset-0 bg-black/50 cursor-default"
      onclick={closeClusterPanel}
      aria-label="패널 닫기"></button>
    <div class="absolute right-0 top-14 bottom-0 w-full md:w-[75vw] max-w-5xl
                bg-gray-950 border-l border-gray-700 overflow-y-auto shadow-2xl">
      <K3sClusterDetailPanel clusterId={selectedClusterId} onClose={closeClusterPanel} />
    </div>
  </div>
{/if}

<div class="p-4 md:p-8">
  <div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold text-white">k3s 클러스터</h1>
    <div class="flex items-center gap-2">
      <button
        onclick={() => { showDeleted = !showDeleted; fetchClusters(); }}
        class="text-xs px-3 py-1.5 rounded border transition-colors {showDeleted ? 'border-gray-500 text-gray-300 bg-gray-800' : 'border-gray-700 text-gray-500 hover:border-gray-500 hover:text-gray-400'}"
      >
        {showDeleted ? '삭제 이력 숨기기' : '삭제 이력 보기'}
      </button>
      <AutoRefreshToggle bind:active={autoRefresh} intervalSeconds={5} />
      <RefreshButton {refreshing} onclick={forceRefresh} />
      <button onclick={openCreateModal}
        class="bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
        + 클러스터 생성
      </button>
    </div>
  </div>

  <p class="text-sm text-gray-500 mb-6">Nova VM + cloud-init으로 k3s Kubernetes 클러스터를 프로비저닝합니다.</p>

  {#if error}
    <div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>
  {/if}

  {#if loading}
    <LoadingSkeleton variant="table" rows={3} />
  {:else if clusters.length === 0}
    <div class="text-center py-20 text-gray-600">
      <div class="text-5xl mb-4">☸</div>
      <p class="text-lg">k3s 클러스터가 없습니다</p>
      <button onclick={openCreateModal} class="text-blue-400 hover:text-blue-300 text-sm mt-2 inline-block">
        첫 클러스터를 생성하세요 →
      </button>
    </div>
  {:else}
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
            <th class="text-left py-3 pr-6">이름</th>
            <th class="text-left py-3 pr-6">상태</th>
            <th class="text-left py-3 pr-6">에이전트</th>
            <th class="text-left py-3 pr-6">API 주소</th>
            <th class="text-left py-3 pr-6">k3s 버전</th>
            <th class="text-left py-3 pr-6">생성일</th>
            <th class="text-right py-3">액션</th>
          </tr>
        </thead>
        <tbody>
          {#each clusters as cluster (cluster.id)}
            <tr
              class="border-b border-gray-800/50 transition-colors {cluster.deleted_at ? 'opacity-50' : 'hover:bg-gray-800/30 cursor-pointer'}"
              onclick={() => !cluster.deleted_at && openClusterPanel(cluster.id)}
              onkeydown={(e) => e.key === 'Enter' && !cluster.deleted_at && openClusterPanel(cluster.id)}
              role="button"
              tabindex="0">
              <td class="py-3 pr-6">
                <span class="font-medium {cluster.deleted_at ? 'text-gray-500 line-through' : 'text-white hover:text-blue-400'} transition-colors">
                  {cluster.name}
                </span>
                {#if cluster.deleted_at}
                  <div class="text-xs text-gray-600 mt-0.5">
                    삭제됨 {cluster.deleted_at.replace('T', ' ').slice(0, 16)}
                  </div>
                {:else if cluster.status_reason}
                  <div class="text-xs text-gray-500 truncate max-w-xs">{cluster.status_reason}</div>
                {/if}
              </td>
              <td class="py-3 pr-6">
                <span class="px-2 py-0.5 rounded text-xs font-medium {statusColor[cluster.status] ?? 'text-gray-400 bg-gray-800'}">
                  {cluster.status}
                </span>
              </td>
              <td class="py-3 pr-6 text-gray-400 text-xs">
                {cluster.agent_vm_ids.length} / {cluster.agent_count}
              </td>
              <td class="py-3 pr-6 font-mono text-xs text-gray-400">
                {cluster.api_address || '-'}
              </td>
              <td class="py-3 pr-6 text-xs text-gray-500">
                {cluster.k3s_version || '-'}
              </td>
              <td class="py-3 pr-6 text-xs text-gray-500">
                {cluster.created_at ? cluster.created_at.split('T')[0] : '-'}
              </td>
              <td class="py-3 text-right" onclick={(e) => e.stopPropagation()} role="none" onkeydown={(e) => e.stopPropagation()}>
                <div class="flex items-center justify-end gap-2">
                  <button
                    onclick={() => downloadKubeconfig(cluster.id, cluster.name)}
                    disabled={cluster.status !== 'ACTIVE'}
                    class="text-blue-400 hover:text-blue-300 disabled:text-gray-600 text-xs px-2 py-1 rounded border border-blue-900 hover:border-blue-700 disabled:border-gray-700 transition-colors">
                    kubeconfig
                  </button>
                  {#if !cluster.deleted_at}
                  <button
                    onclick={() => deleteCluster(cluster.id, cluster.name)}
                    disabled={deleting === cluster.id || cluster.status === 'DELETING'}
                    class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-1 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors">
                    {deleting === cluster.id ? '삭제 중...' : '삭제'}
                  </button>
                  {/if}
                </div>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
