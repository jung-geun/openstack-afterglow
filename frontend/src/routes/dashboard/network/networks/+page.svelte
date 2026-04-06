<script lang="ts">
  import { auth } from '$lib/stores/auth';
  import { untrack } from 'svelte';
  import { api, ApiError, memoryCache } from '$lib/api/client';
  import { goto } from '$app/navigation';
  import type { Network } from '$lib/types/resources';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';

  const statusColor: Record<string, string> = {
    ACTIVE: 'text-green-400 bg-green-900/30',
    DOWN:   'text-red-400 bg-red-900/30',
    BUILD:  'text-yellow-400 bg-yellow-900/30',
  };

  let networks = $state<Network[]>([]);
  let loading = $state(true);
  let error = $state('');
  let deleting = $state<string | null>(null);
  let showModal = $state(false);
  let creating = $state(false);
  let createError = $state('');
  let form = $state({
    name: '',
    addSubnet: false,
    cidr: '10.0.0.0/24',
    gateway: '',
    dhcp: true,
  });

  function swrGet<T>(path: string): T | null {
    const key = `${path}:${$auth.projectId}`;
    const c = memoryCache.get(key);
    return c ? (c.data as T) : null;
  }
  function swrSet(path: string, data: unknown) {
    memoryCache.set(`${path}:${$auth.projectId}`, { data, timestamp: Date.now() });
  }

  async function fetchNetworks() {
    const path = '/api/networks';
    const cached = swrGet<Network[]>(path);
    if (cached && networks.length === 0) networks = cached;
    try {
      networks = await api.get<Network[]>(path, $auth.token ?? undefined, $auth.projectId ?? undefined);
      swrSet(path, networks);
      error = '';
    } catch (e) {
      if (!cached) error = e instanceof ApiError ? `조회 실패 (${e.status})` : '서버 오류';
    } finally {
      loading = false;
    }
  }

  async function createNetwork() {
    if (!form.name.trim()) return;
    creating = true;
    createError = '';
    try {
      const body: Record<string, unknown> = { name: form.name };
      if (form.addSubnet) {
        body.subnet = {
          cidr: form.cidr,
          gateway_ip: form.gateway || null,
          enable_dhcp: form.dhcp,
        };
      }
      await api.post('/api/networks', body, $auth.token ?? undefined, $auth.projectId ?? undefined);
      showModal = false;
      form = { name: '', addSubnet: false, cidr: '10.0.0.0/24', gateway: '', dhcp: true };
      await fetchNetworks();
    } catch (e) {
      createError = e instanceof ApiError ? e.message : '생성 실패';
    } finally {
      creating = false;
    }
  }

  async function deleteNetwork(id: string, name: string, isExternal: boolean, isShared: boolean) {
    if (isExternal || isShared) { alert('외부/공유 네트워크는 삭제할 수 없습니다.'); return; }
    if (!confirm(`네트워크 "${name || id.slice(0, 8)}"를 삭제하시겠습니까?`)) return;
    deleting = id;
    try {
      await api.delete(`/api/networks/${id}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
      await fetchNetworks();
    } catch (e) {
      alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
    } finally {
      deleting = null;
    }
  }

  $effect(() => {
    const projectId = $auth.projectId;
    if (!projectId) return;
    loading = true;
    untrack(() => { fetchNetworks(); });
  });
</script>

{#if showModal}
  <div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onclick={() => { showModal = false; createError = ''; }} role="dialog" aria-modal="true" tabindex="-1" onkeydown={(e) => e.key === 'Escape' && (showModal = false)}>
    <div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()} role="none" onkeydown={(e) => e.stopPropagation()}>
      <h2 class="text-lg font-semibold text-white mb-5">네트워크 생성</h2>
      <div class="space-y-4">
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름
            <input bind:value={form.name} type="text" placeholder="my-network" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
          </label>
        </div>
        <div class="flex items-center gap-2">
          <input type="checkbox" id="addSubnet" bind:checked={form.addSubnet} class="rounded border-gray-600" />
          <label for="addSubnet" class="text-sm text-gray-300">서브넷 함께 생성</label>
        </div>
        {#if form.addSubnet}
          <div>
            <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">CIDR
              <input bind:value={form.cidr} type="text" placeholder="10.0.0.0/24" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm font-mono focus:outline-none focus:border-blue-500 mt-1.5" />
            </label>
          </div>
          <div>
            <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">게이트웨이 (선택)
              <input bind:value={form.gateway} type="text" placeholder="10.0.0.1" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm font-mono focus:outline-none focus:border-blue-500 mt-1.5" />
            </label>
          </div>
          <div class="flex items-center gap-2">
            <input type="checkbox" id="dhcp" bind:checked={form.dhcp} class="rounded border-gray-600" />
            <label for="dhcp" class="text-sm text-gray-300">DHCP 활성화</label>
          </div>
        {/if}
      </div>
      {#if createError}<div class="mt-4 text-red-400 text-xs bg-red-900/20 border border-red-800 rounded px-3 py-2">{createError}</div>{/if}
      <div class="flex justify-end gap-3 mt-6">
        <button onclick={() => { showModal = false; createError = ''; }} class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">취소</button>
        <button onclick={createNetwork} disabled={creating} class="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors">{creating ? '생성 중...' : '생성'}</button>
      </div>
    </div>
  </div>
{/if}

<div class="p-8">
  <div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold text-white">네트워크</h1>
    <button onclick={() => showModal = true} class="bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">+ 네트워크 생성</button>
  </div>

  {#if error}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>{/if}

  {#if loading}
    <LoadingSkeleton variant="table" rows={5} />
  {:else if networks.length === 0}
    <div class="text-center py-20 text-gray-600">
      <div class="text-5xl mb-4">🌐</div>
      <p class="text-lg">네트워크가 없습니다</p>
    </div>
  {:else}
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
            <th class="text-left py-3 pr-6">이름</th>
            <th class="text-left py-3 pr-6">상태</th>
            <th class="text-left py-3 pr-6">서브넷</th>
            <th class="text-left py-3 pr-6">유형</th>
            <th class="text-right py-3">액션</th>
          </tr>
        </thead>
        <tbody>
          {#each networks as net (net.id)}
            <tr onclick={() => goto('/dashboard/network/networks/' + net.id)} class="border-b border-gray-800/50 hover:bg-gray-800/50 transition-colors cursor-pointer">
              <td class="py-3 pr-6 font-medium text-white">{net.name || net.id.slice(0, 12)}</td>
              <td class="py-3 pr-6"><span class="px-2 py-0.5 rounded text-xs font-medium {statusColor[net.status] ?? 'text-gray-400 bg-gray-800'}">{net.status}</span></td>
              <td class="py-3 pr-6 text-gray-400 text-xs">{net.subnets.length}개</td>
              <td class="py-3 pr-6 text-xs">
                <div class="flex gap-1 flex-wrap">
                  {#if net.is_external}<span class="px-1.5 py-0.5 bg-orange-900/40 text-orange-300 rounded">외부</span>{/if}
                  {#if net.is_shared}<span class="px-1.5 py-0.5 bg-teal-900/40 text-teal-300 rounded">공유</span>{/if}
                  {#if !net.is_external && !net.is_shared}<span class="px-1.5 py-0.5 bg-blue-900/40 text-blue-300 rounded">내부</span>{/if}
                </div>
              </td>
              <td class="py-3 text-right">
                {#if !net.is_external && !net.is_shared}
                  <button onclick={(e) => { e.stopPropagation(); deleteNetwork(net.id, net.name, net.is_external, net.is_shared); }} disabled={deleting === net.id} class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-1 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors">
                    {deleting === net.id ? '삭제 중...' : '삭제'}
                  </button>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
