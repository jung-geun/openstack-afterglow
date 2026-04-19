<script lang="ts">
  import { auth } from '$lib/stores/auth';
  import { untrack } from 'svelte';
  import { api, ApiError } from '$lib/api/client';
  import type { LoadBalancer } from '$lib/types/resources';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
  import RefreshButton from '$lib/components/RefreshButton.svelte';
  import AutoRefreshToggle from '$lib/components/AutoRefreshToggle.svelte';
  import SlidePanel from '$lib/components/SlidePanel.svelte';
  import LoadBalancerDetailPanel from '$lib/components/LoadBalancerDetailPanel.svelte';

  const statusColor: Record<string, string> = {
    ACTIVE:  'text-green-400 bg-green-900/30',
    ERROR:   'text-red-400 bg-red-900/30',
    PENDING_CREATE: 'text-yellow-400 bg-yellow-900/30',
    PENDING_UPDATE: 'text-yellow-400 bg-yellow-900/30',
    DELETED: 'text-gray-400 bg-gray-800',
  };

  let selectedLbId = $state<string | null>(null);

  function openLbPanel(id: string) {
    selectedLbId = id;
    history.pushState({ lbId: id }, '', `/dashboard/network/loadbalancers/${id}`);
  }
  function closeLbPanel() {
    selectedLbId = null;
    history.pushState({}, '', '/dashboard/network/loadbalancers');
  }

  let loadbalancers = $state<LoadBalancer[]>([]);
  let loading = $state(true);
  let refreshing = $state(false);
  let error = $state('');
  let autoRefresh = $state(false);

  async function fetchLoadbalancers(opts?: { refresh?: boolean }) {
    try {
      loadbalancers = await api.get<LoadBalancer[]>('/api/loadbalancers', $auth.token ?? undefined, $auth.projectId ?? undefined, opts);
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
      await fetchLoadbalancers({ refresh: true });
    } finally {
      refreshing = false;
    }
  }

  $effect(() => {
    const pid = $auth.projectId;
    if (!pid) return;
    untrack(() => { fetchLoadbalancers(); });
  });

  $effect(() => {
    if (!$auth.projectId || !autoRefresh) return;
    const interval = setInterval(() => untrack(() => { fetchLoadbalancers(); }), 30000);
    return () => clearInterval(interval);
  });
</script>

<div class="p-4 md:p-8">
  <div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold text-white">로드밸런서</h1>
    <div class="flex items-center gap-2">
      <AutoRefreshToggle bind:active={autoRefresh} intervalSeconds={30} />
      <RefreshButton {refreshing} onclick={forceRefresh} />
      <a href="/dashboard/network/loadbalancers/new" class="bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">+ 로드밸런서 생성</a>
    </div>
  </div>

  {#if error}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>{/if}

  {#if loading}
    <LoadingSkeleton variant="table" rows={4} />
  {:else if loadbalancers.length === 0}
    <div class="text-center py-20 text-gray-600">
      <div class="text-5xl mb-4">⚖️</div>
      <p class="text-lg">로드밸런서가 없습니다</p>
      <a href="/dashboard/network/loadbalancers/new" class="text-blue-400 hover:text-blue-300 text-sm mt-2 inline-block">첫 로드밸런서를 생성하세요 →</a>
    </div>
  {:else}
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
            <th class="text-left py-3 pr-6">이름</th>
            <th class="text-left py-3 pr-6">상태</th>
            <th class="text-left py-3 pr-6">운영 상태</th>
            <th class="text-left py-3 pr-6">VIP 주소</th>
            <th class="text-right py-3">액션</th>
          </tr>
        </thead>
        <tbody>
          {#each loadbalancers as lb (lb.id)}
            <tr onclick={() => openLbPanel(lb.id)} class="border-b border-gray-800/50 hover:bg-gray-800/50 transition-colors cursor-pointer">
              <td class="py-3 pr-6 font-medium text-white">{lb.name || lb.id.slice(0, 12)}</td>
              <td class="py-3 pr-6"><span class="px-2 py-0.5 rounded text-xs font-medium {statusColor[lb.status] ?? 'text-gray-400 bg-gray-800'}">{lb.status}</span></td>
              <td class="py-3 pr-6 text-xs">
                <span class="{lb.operating_status === 'ONLINE' ? 'text-green-400' : 'text-gray-400'}">{lb.operating_status}</span>
              </td>
              <td class="py-3 pr-6 text-gray-400 text-xs font-mono">{lb.vip_address ?? '-'}</td>
              <td class="py-3 text-right">
                <button onclick={(e) => { e.stopPropagation(); openLbPanel(lb.id); }} class="text-gray-400 hover:text-white text-xs px-2 py-1 rounded border border-gray-700 hover:border-gray-500 transition-colors">상세</button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

{#if selectedLbId}
  <SlidePanel onClose={closeLbPanel}>
    <LoadBalancerDetailPanel
      lbId={selectedLbId}
      onClose={closeLbPanel}
      onDeleted={() => { fetchLoadbalancers(); closeLbPanel(); }}
    />
  </SlidePanel>
{/if}
