<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { auth } from '$lib/stores/auth';
  import { api, ApiError } from '$lib/api/client';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';

  interface ClusterTemplate {
    id: string;
    name: string;
    coe: string;
  }

  interface Cluster {
    id: string;
    name: string;
    status: string;
    status_reason: string | null;
    cluster_template_id: string | null;
    master_count: number;
    node_count: number;
    api_address: string | null;
    created_at: string | null;
  }

  const statusColor: Record<string, string> = {
    CREATE_COMPLETE:    'text-green-400 bg-green-900/30',
    CREATE_IN_PROGRESS: 'text-yellow-400 bg-yellow-900/30',
    DELETE_IN_PROGRESS: 'text-orange-400 bg-orange-900/30',
    CREATE_FAILED:      'text-red-400 bg-red-900/30',
    UPDATE_IN_PROGRESS: 'text-blue-400 bg-blue-900/30',
    UPDATE_COMPLETE:    'text-green-400 bg-green-900/30',
  };

  let clusters = $state<Cluster[]>([]);
  let templates = $state<ClusterTemplate[]>([]);
  let loading = $state(true);
  let error = $state('');
  let deleting = $state<string | null>(null);
  let showModal = $state(false);
  let creating = $state(false);
  let createError = $state('');
  let form = $state({
    name: '',
    cluster_template_id: '',
    node_count: 1,
    master_count: 1,
    keypair: '',
  });

  async function fetchClusters() {
    try {
      clusters = await api.get<Cluster[]>('/api/clusters', $auth.token ?? undefined, $auth.projectId ?? undefined);
      error = '';
    } catch (e) {
      error = e instanceof ApiError ? `조회 실패 (${e.status}): ${e.message}` : '서버 오류';
    } finally {
      loading = false;
    }
  }

  async function fetchTemplates() {
    try {
      templates = await api.get<ClusterTemplate[]>('/api/clusters/templates', $auth.token ?? undefined, $auth.projectId ?? undefined);
      if (templates.length > 0) form.cluster_template_id = templates[0].id;
    } catch {
      templates = [];
    }
  }

  async function createCluster() {
    if (!form.name.trim() || !form.cluster_template_id) return;
    creating = true;
    createError = '';
    try {
      const body: Record<string, unknown> = {
        name: form.name,
        cluster_template_id: form.cluster_template_id,
        node_count: form.node_count,
        master_count: form.master_count,
      };
      if (form.keypair.trim()) body.keypair = form.keypair;
      await api.post('/api/clusters', body, $auth.token ?? undefined, $auth.projectId ?? undefined);
      showModal = false;
      form = { name: '', cluster_template_id: templates[0]?.id ?? '', node_count: 1, master_count: 1, keypair: '' };
      await fetchClusters();
    } catch (e) {
      createError = e instanceof ApiError ? e.message : '생성 실패';
    } finally {
      creating = false;
    }
  }

  async function deleteCluster(id: string, name: string) {
    if (!confirm(`클러스터 "${name}"을 삭제하시겠습니까?`)) return;
    deleting = id;
    try {
      await api.delete(`/api/clusters/${id}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
      await fetchClusters();
    } catch (e) {
      alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
    } finally {
      deleting = null;
    }
  }

  onMount(() => { fetchClusters(); fetchTemplates(); });
</script>

{#if showModal}
  <div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onclick={() => { showModal = false; createError = ''; }} role="dialog" aria-modal="true" tabindex="-1" onkeydown={(e) => e.key === 'Escape' && (showModal = false)}>
    <div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()} role="none" onkeydown={(e) => e.stopPropagation()}>
      <h2 class="text-lg font-semibold text-white mb-5">K8s 클러스터 생성</h2>
      <div class="space-y-4">
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">클러스터 이름
            <input bind:value={form.name} type="text" placeholder="my-cluster" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
          </label>
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">클러스터 템플릿
            <select bind:value={form.cluster_template_id} class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5">
              {#each templates as t}
                <option value={t.id}>{t.name} ({t.coe})</option>
              {/each}
            </select>
          </label>
        </div>
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">마스터 수
              <input bind:value={form.master_count} type="number" min="1" max="5" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
            </label>
          </div>
          <div>
            <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">워커 수
              <input bind:value={form.node_count} type="number" min="1" max="50" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
            </label>
          </div>
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">키페어 (선택)
            <input bind:value={form.keypair} type="text" placeholder="my-keypair" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
          </label>
        </div>
      </div>
      {#if createError}<div class="mt-3 text-red-400 text-xs">{createError}</div>{/if}
      <div class="flex justify-end gap-3 mt-6">
        <button onclick={() => { showModal = false; createError = ''; }} class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">취소</button>
        <button onclick={createCluster} disabled={creating || !form.name || !form.cluster_template_id} class="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors">{creating ? '생성 중...' : '생성'}</button>
      </div>
    </div>
  </div>
{/if}

<div class="p-4 md:p-8">
  <div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold text-white">K8s 클러스터</h1>
    <button onclick={() => showModal = true} class="bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">+ 클러스터 생성</button>
  </div>

  {#if error}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>{/if}

  {#if loading}
    <LoadingSkeleton variant="table" rows={4} />
  {:else if clusters.length === 0}
    <div class="text-center py-20 text-gray-600">
      <p class="text-lg mb-2">K8s 클러스터가 없습니다</p>
      <p class="text-sm">Magnum을 통해 새 클러스터를 생성하세요</p>
    </div>
  {:else}
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
            <th class="text-left py-3 pr-6">이름</th>
            <th class="text-left py-3 pr-6">상태</th>
            <th class="text-left py-3 pr-6">마스터</th>
            <th class="text-left py-3 pr-6">워커</th>
            <th class="text-left py-3 pr-6">API 주소</th>
            <th class="text-left py-3 pr-6">생성일</th>
            <th class="text-left py-3"></th>
          </tr>
        </thead>
        <tbody>
          {#each clusters as c (c.id)}
            <tr class="border-b border-gray-800/50 hover:bg-gray-800/50 transition-colors">
              <td class="py-3 pr-6">
                <button onclick={() => goto(`/dashboard/containers/clusters/${c.id}`)} class="font-medium text-white hover:text-blue-400 transition-colors text-left">{c.name}</button>
              </td>
              <td class="py-3 pr-6">
                <span class="px-2 py-0.5 rounded text-xs font-medium {statusColor[c.status] ?? 'text-gray-400 bg-gray-800'}">{c.status}</span>
              </td>
              <td class="py-3 pr-6 text-gray-400 text-xs">{c.master_count}</td>
              <td class="py-3 pr-6 text-gray-400 text-xs">{c.node_count}</td>
              <td class="py-3 pr-6 text-gray-400 text-xs font-mono">{c.api_address ?? '-'}</td>
              <td class="py-3 pr-6 text-gray-400 text-xs">{c.created_at?.slice(0, 10) ?? '-'}</td>
              <td class="py-3">
                <button onclick={() => deleteCluster(c.id, c.name)} disabled={deleting === c.id} class="text-xs text-red-400 hover:text-red-300 disabled:opacity-40 transition-colors">
                  {deleting === c.id ? '삭제 중...' : '삭제'}
                </button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
