<script lang="ts">
  import { auth } from '$lib/stores/auth';
  import { untrack } from 'svelte';
  import { api, ApiError } from '$lib/api/client';
  import { goto } from '$app/navigation';
  import type { Router, Network } from '$lib/types/resources';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
  import RefreshButton from '$lib/components/RefreshButton.svelte';
  import AutoRefreshToggle from '$lib/components/AutoRefreshToggle.svelte';

  const statusColor: Record<string, string> = {
    ACTIVE: 'text-green-400 bg-green-900/30',
    DOWN:   'text-red-400 bg-red-900/30',
  };

  let routers = $state<Router[]>([]);
  let externalNetworks = $state<Network[]>([]);
  let loading = $state(true);
  let refreshing = $state(false);
  let error = $state('');
  let autoRefresh = $state(false);
  let showModal = $state(false);
  let creating = $state(false);
  let createError = $state('');
  let form = $state({ name: '', external_network_id: '' });

  async function fetchRouters(opts?: { refresh?: boolean }) {
    try {
      routers = await api.get<Router[]>('/api/routers', $auth.token ?? undefined, $auth.projectId ?? undefined, opts);
      error = '';
    } catch (e) {
      error = e instanceof ApiError ? `조회 실패 (${e.status})` : '서버 오류';
    } finally {
      loading = false;
    }
  }

  async function forceRefresh() {
    refreshing = true;
    try {
      await fetchRouters({ refresh: true });
    } finally {
      refreshing = false;
    }
  }

  async function fetchNetworks() {
    try {
      const nets = await api.get<Network[]>('/api/networks', $auth.token ?? undefined, $auth.projectId ?? undefined);
      externalNetworks = nets.filter(n => n.is_external);
    } catch { /* ignore */ }
  }

  async function createRouter() {
    if (!form.name.trim()) return;
    creating = true;
    createError = '';
    try {
      const body: Record<string, unknown> = { name: form.name };
      if (form.external_network_id) body.external_network_id = form.external_network_id;
      await api.post('/api/routers', body, $auth.token ?? undefined, $auth.projectId ?? undefined);
      showModal = false;
      form = { name: '', external_network_id: '' };
      await fetchRouters();
    } catch (e) {
      createError = e instanceof ApiError ? e.message : '생성 실패';
    } finally {
      creating = false;
    }
  }

  $effect(() => {
    const projectId = $auth.projectId;
    if (!projectId) return;
    loading = true;
    untrack(() => { fetchRouters(); fetchNetworks(); });
  });

  $effect(() => {
    if (!$auth.projectId || !autoRefresh) return;
    const interval = setInterval(() => untrack(() => { fetchRouters(); }), 15000);
    return () => clearInterval(interval);
  });
</script>

{#if showModal}
  <div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onclick={() => { showModal = false; createError = ''; }} role="dialog" aria-modal="true" tabindex="-1" onkeydown={(e) => e.key === 'Escape' && (showModal = false)}>
    <div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()} role="none" onkeydown={(e) => e.stopPropagation()}>
      <h2 class="text-lg font-semibold text-white mb-5">라우터 생성</h2>
      <div class="space-y-4">
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름
            <input bind:value={form.name} type="text" placeholder="my-router" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
          </label>
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">외부 네트워크 (선택)
            <select bind:value={form.external_network_id} class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5">
              <option value="">외부 게이트웨이 없음</option>
              {#each externalNetworks as net}
                <option value={net.id}>{net.name || net.id.slice(0, 12)}</option>
              {/each}
            </select>
          </label>
        </div>
      </div>
      {#if createError}<div class="mt-4 text-red-400 text-xs bg-red-900/20 border border-red-800 rounded px-3 py-2">{createError}</div>{/if}
      <div class="flex justify-end gap-3 mt-6">
        <button onclick={() => { showModal = false; createError = ''; }} class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">취소</button>
        <button onclick={createRouter} disabled={creating} class="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors">{creating ? '생성 중...' : '생성'}</button>
      </div>
    </div>
  </div>
{/if}

<div class="p-4 md:p-8">
  <div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold text-white">라우터</h1>
    <div class="flex items-center gap-2">
      <AutoRefreshToggle bind:active={autoRefresh} intervalSeconds={15} />
      <RefreshButton {refreshing} onclick={forceRefresh} />
      <button onclick={() => showModal = true} class="bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">+ 라우터 생성</button>
    </div>
  </div>

  {#if error}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>{/if}

  {#if loading}
    <LoadingSkeleton variant="table" rows={4} />
  {:else if routers.length === 0}
    <div class="text-center py-20 text-gray-600">
      <div class="text-5xl mb-4">🔀</div>
      <p class="text-lg">라우터가 없습니다</p>
    </div>
  {:else}
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
            <th class="text-left py-3 pr-6">이름</th>
            <th class="text-left py-3 pr-6">상태</th>
            <th class="text-left py-3 pr-6">외부 게이트웨이</th>
            <th class="text-left py-3 pr-6">연결된 서브넷</th>
            <th class="text-right py-3">액션</th>
          </tr>
        </thead>
        <tbody>
          {#each routers as router (router.id)}
            <tr onclick={() => goto('/dashboard/network/routers/' + router.id)} onkeydown={(e) => e.key === 'Enter' && goto('/dashboard/network/routers/' + router.id)} tabindex="0" role="link" class="border-b border-gray-800/50 hover:bg-gray-800/50 transition-colors cursor-pointer">
              <td class="py-3 pr-6 font-medium text-white">{router.name || router.id.slice(0, 12)}</td>
              <td class="py-3 pr-6"><span class="px-2 py-0.5 rounded text-xs font-medium {statusColor[router.status] ?? 'text-gray-400 bg-gray-800'}">{router.status}</span></td>
              <td class="py-3 pr-6 text-xs">
                {#if router.external_gateway_network_id}
                  <span class="text-orange-300 font-mono">{router.external_gateway_network_id.slice(0, 12)}…</span>
                {:else}
                  <span class="text-gray-600">-</span>
                {/if}
              </td>
              <td class="py-3 pr-6 text-gray-400 text-xs">{router.connected_subnet_ids.length}개</td>
              <td class="py-3 text-right">
                <button onclick={(e) => { e.stopPropagation(); goto('/dashboard/network/routers/' + router.id); }} class="text-gray-400 hover:text-white text-xs px-2 py-1 rounded border border-gray-700 hover:border-gray-500 transition-colors">상세</button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
