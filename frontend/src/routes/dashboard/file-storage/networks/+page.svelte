<script lang="ts">
  import { auth } from '$lib/stores/auth';
  import { untrack } from 'svelte';
  import { api, ApiError } from '$lib/api/client';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
  import RefreshButton from '$lib/components/RefreshButton.svelte';

  interface ShareNetwork {
    id: string;
    name: string;
    description: string;
    neutron_net_id: string | null;
    neutron_subnet_id: string | null;
    status: string;
    created_at: string | null;
  }

  interface NeutronNetwork {
    id: string;
    name: string;
    status: string;
    subnets: string[];
  }

  interface Subnet {
    id: string;
    name: string;
    cidr: string;
  }

  const statusColor: Record<string, string> = {
    active:  'text-green-400 bg-green-900/30',
    error:   'text-red-400 bg-red-900/30',
    inactive: 'text-gray-400 bg-gray-800',
  };

  let networks = $state<ShareNetwork[]>([]);
  let neutronNetworks = $state<NeutronNetwork[]>([]);
  let subnets = $state<Subnet[]>([]);
  let loading = $state(true);
  let refreshing = $state(false);
  let deleting = $state<string | null>(null);
  let error = $state('');
  let showModal = $state(false);
  let creating = $state(false);
  let createError = $state('');
  let form = $state({ name: '', description: '', neutron_net_id: '', neutron_subnet_id: '' });
  let loadingSubnets = $state(false);

  const token = $derived($auth.token ?? undefined);
  const projectId = $derived($auth.projectId ?? undefined);

  async function fetchNetworks(opts?: { refresh?: boolean }) {
    try {
      networks = await api.get<ShareNetwork[]>('/api/share-networks', token, projectId, opts);
      error = '';
    } catch (e) {
      error = e instanceof ApiError ? `조회 실패 (${e.status})` : '서버 오류';
    } finally {
      loading = false;
    }
  }

  async function openCreateModal() {
    showModal = true;
    form = { name: '', description: '', neutron_net_id: '', neutron_subnet_id: '' };
    subnets = [];
    createError = '';
    try {
      neutronNetworks = await api.get<NeutronNetwork[]>('/api/networks', token, projectId);
    } catch {
      neutronNetworks = [];
    }
  }

  async function onNetworkChange() {
    form.neutron_subnet_id = '';
    subnets = [];
    if (!form.neutron_net_id) return;
    loadingSubnets = true;
    try {
      const detail = await api.get<{ id: string; subnet_details: Subnet[] }>(
        `/api/networks/${form.neutron_net_id}`, token, projectId
      );
      subnets = detail.subnet_details ?? [];
    } catch {
      subnets = [];
    } finally {
      loadingSubnets = false;
    }
  }

  async function createNetwork() {
    if (!form.name.trim() || !form.neutron_net_id || !form.neutron_subnet_id) return;
    creating = true;
    createError = '';
    try {
      await api.post('/api/share-networks', {
        name: form.name,
        description: form.description,
        neutron_net_id: form.neutron_net_id,
        neutron_subnet_id: form.neutron_subnet_id,
      }, token, projectId);
      showModal = false;
      await fetchNetworks();
    } catch (e) {
      createError = e instanceof ApiError ? e.message : '생성 실패';
    } finally {
      creating = false;
    }
  }

  async function deleteNetwork(id: string, name: string) {
    if (!confirm(`Share 네트워크 "${name || id.slice(0, 8)}"을 삭제하시겠습니까?\n이 네트워크를 사용 중인 파일 스토리지가 있으면 삭제할 수 없습니다.`)) return;
    deleting = id;
    try {
      await api.delete(`/api/share-networks/${id}`, token, projectId);
      await fetchNetworks();
    } catch (e) {
      alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
    } finally {
      deleting = null;
    }
  }

  async function forceRefresh() {
    refreshing = true;
    try {
      await fetchNetworks({ refresh: true });
    } finally {
      refreshing = false;
    }
  }

  $effect(() => {
    if (!$auth.projectId) return;
    loading = true;
    untrack(() => fetchNetworks());
  });
</script>

{#if showModal}
  <div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
    onclick={() => { showModal = false; createError = ''; }}
    role="dialog" aria-modal="true" tabindex="-1"
    onkeydown={(e) => e.key === 'Escape' && (showModal = false)}>
    <div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-lg mx-4 shadow-2xl"
      onclick={(e) => e.stopPropagation()} role="none" onkeydown={(e) => e.stopPropagation()}>
      <h2 class="text-lg font-semibold text-white mb-5">Share 네트워크 생성</h2>
      <div class="space-y-4">
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름 *
            <input bind:value={form.name} type="text" placeholder="my-share-network"
              class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
          </label>
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">설명 (선택)
            <input bind:value={form.description} type="text" placeholder="설명"
              class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
          </label>
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">Neutron 네트워크 *
            <select bind:value={form.neutron_net_id} onchange={onNetworkChange}
              class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5">
              <option value="">네트워크 선택</option>
              {#each neutronNetworks as net}
                <option value={net.id}>{net.name || net.id.slice(0, 12)} ({net.status})</option>
              {/each}
            </select>
          </label>
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">서브넷 *
            {#if loadingSubnets}
              <div class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-gray-500 text-sm mt-1.5">로딩 중...</div>
            {:else}
              <select bind:value={form.neutron_subnet_id}
                disabled={subnets.length === 0}
                class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5 disabled:text-gray-600">
                <option value="">{subnets.length === 0 ? '네트워크를 먼저 선택하세요' : '서브넷 선택'}</option>
                {#each subnets as subnet}
                  <option value={subnet.id}>{subnet.name || subnet.id.slice(0, 12)} {subnet.cidr ? `(${subnet.cidr})` : ''}</option>
                {/each}
              </select>
            {/if}
          </label>
        </div>
      </div>
      {#if createError}
        <div class="mt-4 text-red-400 text-xs bg-red-900/20 border border-red-800 rounded px-3 py-2">{createError}</div>
      {/if}
      <div class="flex justify-end gap-3 mt-6">
        <button onclick={() => { showModal = false; createError = ''; }}
          class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">취소</button>
        <button onclick={createNetwork} disabled={creating || !form.name.trim() || !form.neutron_net_id || !form.neutron_subnet_id}
          class="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors">
          {creating ? '생성 중...' : '생성'}
        </button>
      </div>
    </div>
  </div>
{/if}

<div class="p-4 md:p-8">
  <div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold text-white">Share 네트워크</h1>
    <div class="flex items-center gap-2">
      <RefreshButton {refreshing} onclick={forceRefresh} />
      <button onclick={openCreateModal}
        class="bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
        + Share 네트워크 생성
      </button>
    </div>
  </div>

  <p class="text-sm text-gray-500 mb-6">파일 스토리지(Manila)를 Neutron 네트워크에 연결하는 Share Network를 관리합니다. NFS 프로토콜 사용 시 필수입니다.</p>

  {#if error}
    <div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>
  {/if}

  {#if loading}
    <LoadingSkeleton variant="table" rows={4} />
  {:else if networks.length === 0}
    <div class="text-center py-20 text-gray-600">
      <div class="text-5xl mb-4">🔗</div>
      <p class="text-lg">Share 네트워크가 없습니다</p>
      <button onclick={openCreateModal} class="text-blue-400 hover:text-blue-300 text-sm mt-2 inline-block">
        첫 Share 네트워크를 생성하세요 →
      </button>
    </div>
  {:else}
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
            <th class="text-left py-3 pr-6">이름</th>
            <th class="text-left py-3 pr-6">상태</th>
            <th class="text-left py-3 pr-6">Neutron 네트워크 ID</th>
            <th class="text-left py-3 pr-6">서브넷 ID</th>
            <th class="text-left py-3 pr-6">생성일</th>
            <th class="text-right py-3">액션</th>
          </tr>
        </thead>
        <tbody>
          {#each networks as net (net.id)}
            <tr class="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
              <td class="py-3 pr-6 font-medium text-white">
                {#if net.name}{net.name}{:else}<span class="text-gray-400 font-mono text-xs">{net.id.slice(0, 8)}</span>{/if}
                {#if net.description}
                  <div class="text-xs text-gray-500">{net.description}</div>
                {/if}
              </td>
              <td class="py-3 pr-6">
                <span class="px-2 py-0.5 rounded text-xs font-medium {statusColor[net.status] ?? 'text-gray-400 bg-gray-800'}">
                  {net.status || '-'}
                </span>
              </td>
              <td class="py-3 pr-6 font-mono text-xs text-gray-400">{net.neutron_net_id?.slice(0, 20) ?? '-'}...</td>
              <td class="py-3 pr-6 font-mono text-xs text-gray-400">{net.neutron_subnet_id?.slice(0, 20) ?? '-'}...</td>
              <td class="py-3 pr-6 text-xs text-gray-500">{net.created_at ? net.created_at.split('T')[0] : '-'}</td>
              <td class="py-3 text-right">
                <button onclick={() => deleteNetwork(net.id, net.name)}
                  disabled={deleting === net.id}
                  class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-1 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors">
                  {deleting === net.id ? '삭제 중...' : '삭제'}
                </button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
