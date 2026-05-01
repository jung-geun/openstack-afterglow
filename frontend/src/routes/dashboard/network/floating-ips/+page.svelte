<script lang="ts">
  import { untrack } from 'svelte';
  import { auth } from '$lib/stores/auth';
  import { api, ApiError } from '$lib/api/client';
  import type { FloatingIp } from '$lib/types/resources';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
  import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
  import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
  import StatusChip from '$lib/components/ui/StatusChip.svelte';
  import PageHeader from '$lib/components/ui/PageHeader.svelte';

  let fips = $state<FloatingIp[]>([]);
  let loading = $state(true);
  let refreshing = $state(false);
  let error = $state('');
  let deleting = $state<string | null>(null);

  async function load(opts?: { refresh?: boolean }) {
    error = '';
    try {
      fips = await api.get<FloatingIp[]>(
        '/api/networks/floating-ips',
        $auth.token ?? undefined,
        $auth.projectId ?? undefined,
        opts,
      );
    } catch (e) {
      error = e instanceof ApiError ? e.message : '목록을 불러올 수 없습니다';
    } finally {
      loading = false;
    }
  }

  async function forceRefresh() {
    refreshing = true;
    try {
      await load({ refresh: true });
    } finally {
      refreshing = false;
    }
  }

  async function deleteFip(id: string, addr: string) {
    if (!confirm(`Floating IP "${addr}"를 해제하시겠습니까?`)) return;
    deleting = id;
    try {
      await api.delete(`/api/networks/floating-ips/${id}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
      await load();
    } catch (e) {
      alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
    } finally {
      deleting = null;
    }
  }

  const ar = createAutoRefresh(() => load(), {
    storageKey: 'network-floating-ips',
    defaultActive: false,
    defaultInterval: 30,
    intervalOptions: [10, 15, 30, 60],
  });

  $effect(() => {
    const pid = $auth.projectId;
    if (!pid) return;
    untrack(() => load());
  });
</script>

<div class="p-4 md:p-8 max-w-5xl">
  <PageHeader breadcrumb="네트워크" title="Floating IP">
    {#snippet actions()}
      <AutoRefreshControl
        bind:active={ar.active}
        bind:intervalSeconds={ar.intervalSeconds}
        intervalOptions={ar.intervalOptions}
        refreshing={refreshing}
        onManualRefresh={forceRefresh}
      />
    {/snippet}
  </PageHeader>

  {#if error}
    <div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>
  {/if}

  {#if loading}
    <LoadingSkeleton rows={4} />
  {:else}
    <div class="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
      <div class="grid grid-cols-[1fr_160px_1fr_140px_90px] px-5 py-3 border-b border-gray-800 text-[11px] uppercase tracking-wider text-gray-500 font-medium">
        <div>Floating IP</div>
        <div>연결된 Fixed IP</div>
        <div>인스턴스</div>
        <div>상태</div>
        <div></div>
      </div>

      {#each fips as fip (fip.id)}
        <div class="grid grid-cols-[1fr_160px_1fr_140px_90px] px-5 py-3.5 border-b border-gray-800 last:border-b-0 items-center hover:bg-gray-800/20 transition-colors">
          <div class="font-mono text-[13px] text-white">{fip.floating_ip_address}</div>
          <div class="text-[12px] text-gray-400 font-mono truncate">
            {fip.fixed_ip_address ?? '—'}
          </div>
          <div class="text-[12px] truncate">
            {#if fip.instance_name}
              <span class="text-blue-400">{fip.instance_name}</span>
            {:else if fip.instance_id}
              <span class="text-gray-400 font-mono">{fip.instance_id.slice(0, 8)}…</span>
            {:else}
              <span class="text-gray-600">—</span>
            {/if}
          </div>
          <div><StatusChip status={fip.status} /></div>
          <div class="flex justify-end">
            <button
              onclick={() => deleteFip(fip.id, fip.floating_ip_address)}
              disabled={deleting === fip.id}
              class="text-[11px] text-red-400 hover:text-red-300 transition-colors disabled:opacity-40"
            >
              {deleting === fip.id ? '처리 중...' : '해제'}
            </button>
          </div>
        </div>
      {/each}

      {#if fips.length === 0}
        <div class="text-gray-500 text-sm text-center py-12">할당된 Floating IP가 없습니다</div>
      {/if}
    </div>
  {/if}
</div>
