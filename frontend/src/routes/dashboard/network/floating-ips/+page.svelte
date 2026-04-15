<script lang="ts">
  import { auth } from '$lib/stores/auth';
  import { untrack } from 'svelte';
  import { api, ApiError } from '$lib/api/client';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
  import RefreshButton from '$lib/components/RefreshButton.svelte';
  import AutoRefreshToggle from '$lib/components/AutoRefreshToggle.svelte';

  interface FloatingIp {
    id: string;
    floating_ip_address: string;
    status: string;
    fixed_ip_address: string | null;
    port_id: string | null;
  }

  let floatingIps = $state<FloatingIp[]>([]);
  let loading = $state(true);
  let refreshing = $state(false);
  let error = $state('');
  let autoRefresh = $state(false);
  let creating = $state(false);
  let deleting = $state<string | null>(null);

  const statusColor: Record<string, string> = {
    ACTIVE: 'text-green-400 bg-green-900/30',
    DOWN:   'text-gray-400 bg-gray-800',
    ERROR:  'text-red-400 bg-red-900/30',
  };

  async function fetchFloatingIps(opts?: { refresh?: boolean }) {
    try {
      floatingIps = await api.get<FloatingIp[]>('/api/networks/floating-ips', $auth.token ?? undefined, $auth.projectId ?? undefined, opts);
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
      await fetchFloatingIps({ refresh: true });
    } finally {
      refreshing = false;
    }
  }

  $effect(() => {
    const pid = $auth.projectId;
    if (!pid) return;
    untrack(() => { fetchFloatingIps(); });
  });

  $effect(() => {
    if (!$auth.projectId || !autoRefresh) return;
    const interval = setInterval(() => untrack(() => { fetchFloatingIps(); }), 15000);
    return () => clearInterval(interval);
  });

  async function allocateFloatingIp() {
    creating = true;
    try {
      await api.post('/api/networks/floating-ips', {}, $auth.token ?? undefined, $auth.projectId ?? undefined);
      await fetchFloatingIps();
    } catch (e) {
      alert('Floating IP 할당 실패: ' + (e instanceof ApiError ? e.message : String(e)));
    } finally {
      creating = false;
    }
  }

  async function releaseFloatingIp(id: string, ip: string) {
    if (!confirm(`Floating IP "${ip}"를 해제하시겠습니까?`)) return;
    deleting = id;
    try {
      await api.delete(`/api/networks/floating-ips/${id}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
      await fetchFloatingIps();
    } catch (e) {
      alert('해제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
    } finally {
      deleting = null;
    }
  }

</script>

<div class="p-4 md:p-8">
  <div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold text-white">Floating IP</h1>
    <div class="flex items-center gap-2">
      <AutoRefreshToggle bind:active={autoRefresh} intervalSeconds={15} />
      <RefreshButton {refreshing} onclick={forceRefresh} />
      <button onclick={allocateFloatingIp} disabled={creating} class="bg-gray-700 hover:bg-gray-600 disabled:bg-gray-800 disabled:text-gray-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
        {creating ? '할당 중...' : '+ Floating IP 할당'}
      </button>
    </div>
  </div>

  {#if error}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>{/if}

  {#if loading}
    <LoadingSkeleton variant="table" rows={4} />
  {:else if floatingIps.length === 0}
    <div class="text-center py-20 text-gray-600">
      <div class="text-5xl mb-4">🌐</div>
      <p class="text-lg">Floating IP가 없습니다</p>
    </div>
  {:else}
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
            <th class="text-left py-3 pr-6">Floating IP</th>
            <th class="text-left py-3 pr-6">상태</th>
            <th class="text-left py-3 pr-6">연결된 IP</th>
            <th class="text-right py-3">액션</th>
          </tr>
        </thead>
        <tbody>
          {#each floatingIps as fip (fip.id)}
            <tr class="border-b border-gray-800/50">
              <td class="py-3 pr-6 font-mono text-white">{fip.floating_ip_address}</td>
              <td class="py-3 pr-6"><span class="px-2 py-0.5 rounded text-xs font-medium {statusColor[fip.status] ?? 'text-gray-400 bg-gray-800'}">{fip.status}</span></td>
              <td class="py-3 pr-6 text-gray-400 text-xs font-mono">{fip.fixed_ip_address ?? '미연결'}</td>
              <td class="py-3 text-right">
                <button onclick={() => releaseFloatingIp(fip.id, fip.floating_ip_address)} disabled={deleting === fip.id || !!fip.port_id} class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-1 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors" title={fip.port_id ? '연결된 IP는 먼저 연결 해제해야 합니다' : ''}>
                  {deleting === fip.id ? '해제 중...' : '해제'}
                </button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
