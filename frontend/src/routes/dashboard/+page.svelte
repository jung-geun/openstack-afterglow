<script lang="ts">
  import { untrack } from 'svelte';
  import { auth, authReady } from '$lib/stores/auth';
  import { api } from '$lib/api/client';
  import type { DashboardSummary } from '$lib/types/resources';
  import type { Instance } from '$lib/types/resources';
  import { formatStorage } from '$lib/utils/format';
  import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
  import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
  import StatTile from '$lib/components/ui/StatTile.svelte';
  import QuotaBar from '$lib/components/ui/QuotaBar.svelte';
  import StatusChip from '$lib/components/ui/StatusChip.svelte';
  import GradientText from '$lib/components/ui/GradientText.svelte';

  interface QuotaItem { limit: number; in_use: number; }
  interface Quotas {
    compute: { instances: QuotaItem; cores: QuotaItem; ram: QuotaItem; };
    storage: { volumes: QuotaItem; gigabytes: QuotaItem; };
    network: { floatingip: QuotaItem; };
    file_storage: { shares: QuotaItem; gigabytes: QuotaItem; };
  }

  let summary = $state<DashboardSummary | null>(null);
  let summaryLoading = $state(true);
  let quotas = $state<Quotas | null>(null);
  let recentInstances = $state<Instance[]>([]);
  let k3sCount = $state<number | null>(null);
  let refreshing = $state(false);

  const token = $derived($auth.token ?? undefined);
  const projectId = $derived($auth.projectId ?? undefined);

  let inFlight: AbortController | null = null;

  async function fetchAll(opts?: { refresh?: boolean }) {
    inFlight?.abort();
    const ctrl = new AbortController();
    inFlight = ctrl;
    if (!summary) summaryLoading = true;
    try {
      await Promise.allSettled([
        api.get<DashboardSummary>('/api/dashboard/summary', token, projectId, { ...opts, signal: ctrl.signal })
          .then(v  => { if (!ctrl.signal.aborted) { summary = v; summaryLoading = false; } })
          .catch(() => { summaryLoading = false; }),
        api.get<Quotas>('/api/dashboard/quotas', token, projectId, { signal: ctrl.signal })
          .then(v => { if (!ctrl.signal.aborted) quotas = v; })
          .catch(() => {}),
        api.get<Instance[]>('/api/instances', token, projectId, { ...opts, signal: ctrl.signal })
          .then(v => { if (!ctrl.signal.aborted) recentInstances = v.slice(0, 5); })
          .catch(() => {}),
        api.get<unknown[]>('/api/k3s/clusters', token, projectId, { signal: ctrl.signal })
          .then(v => { if (!ctrl.signal.aborted) k3sCount = v.filter((c: any) => c.status === 'ACTIVE' || c.provisioning_status === 'ACTIVE').length; })
          .catch(() => { k3sCount = null; }),
      ]);
    } finally {
      if (inFlight === ctrl) inFlight = null;
      summaryLoading = false;
    }
  }

  async function forceRefresh() {
    refreshing = true;
    try { await fetchAll({ refresh: true }); }
    finally { refreshing = false; }
  }

  const ar = createAutoRefresh(() => fetchAll(), {
    storageKey: 'dashboard-home',
    defaultActive: true,
    defaultInterval: 30,
    intervalOptions: [10, 15, 30, 60],
    invokeOnMount: false,
  });

  $effect(() => {
    const pid = $auth.projectId;
    const ready = $authReady;
    if (!pid || !ready) return;
    untrack(() => fetchAll());
  });

  function getFirstIp(inst: Instance): string {
    return inst.ip_addresses?.[0]?.addr ?? '—';
  }
</script>

<div class="p-6 max-w-7xl mx-auto flex flex-col gap-5">
  <!-- 헤더 -->
  <div class="flex items-start justify-between">
    <div>
      <div class="text-[11px] text-gray-500 uppercase tracking-widest font-medium mb-1">OVERVIEW · 대시보드</div>
      <h1 class="text-2xl font-bold text-white mb-1">안녕하세요, <GradientText>{$auth.username}</GradientText>님</h1>
      <div class="text-gray-400 text-[13px]">
        {$auth.projectName ?? '—'} · 최근 동기화 방금 전
      </div>
    </div>
    <AutoRefreshControl
      bind:active={ar.active}
      bind:intervalSeconds={ar.intervalSeconds}
      intervalOptions={ar.intervalOptions}
      refreshing={refreshing}
      onManualRefresh={forceRefresh}
    />
  </div>

  <!-- StatTiles (4개) -->
  {#if summaryLoading && !summary}
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
      {#each Array(4) as _}
        <div class="bg-gray-900 border border-gray-800 rounded-2xl p-[18px] animate-pulse h-[82px]"></div>
      {/each}
    </div>
  {:else}
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
      <!-- 인스턴스 -->
      <StatTile
        label="인스턴스"
        value={summary?.instances.active ?? 0}
        unit={summary ? `/ ${summary.instances.total}` : undefined}
        accent="blue"
      >
        {#snippet icon()}
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2"/></svg>
        {/snippet}
      </StatTile>

      <!-- 블록 볼륨 -->
      <StatTile
        label="블록 볼륨"
        value={summary?.storage.volumes_used ?? 0}
        unit={summary && summary.storage.volumes_limit > 0 ? `/ ${summary.storage.volumes_limit}` : undefined}
        accent="cyan"
      >
        {#snippet icon()}
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4"/></svg>
        {/snippet}
      </StatTile>

      <!-- Floating IP -->
      <StatTile
        label="Floating IP"
        value={quotas?.network.floatingip.in_use ?? 0}
        unit={quotas && quotas.network.floatingip.limit > 0 ? `/ ${quotas.network.floatingip.limit}` : undefined}
        accent="violet"
      >
        {#snippet icon()}
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9"/></svg>
        {/snippet}
      </StatTile>

      <!-- Drover 클러스터 -->
      <StatTile
        label="Drover 클러스터"
        value={k3sCount ?? '—'}
        unit={k3sCount !== null ? '활성' : undefined}
        accent="emerald"
      >
        {#snippet icon()}
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 2l8 4v6c0 5.55 3.84 10.74 8 12 0 0-4.5 1.5-8 0C8.16 22.74 4 17.55 4 12V6l8-4z"/></svg>
        {/snippet}
      </StatTile>
    </div>
  {/if}

  <!-- 2-column: 최근 인스턴스 + 쿼터 사용률 -->
  <div class="grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-3.5">
    <!-- 최근 인스턴스 -->
    <div class="bg-gray-900 border border-gray-800 rounded-2xl p-5">
      <div class="flex items-center mb-3.5">
        <div class="text-white text-[15px] font-semibold">최근 인스턴스</div>
        <a href="/dashboard/compute/instances" class="ml-auto text-[13px] text-gray-500 hover:text-gray-200 transition-colors">모두 보기 →</a>
      </div>
      {#if summaryLoading && recentInstances.length === 0}
        <div class="space-y-2">
          {#each Array(4) as _}
            <div class="h-10 bg-gray-800 rounded animate-pulse"></div>
          {/each}
        </div>
      {:else if recentInstances.length === 0}
        <div class="text-gray-600 text-sm py-6 text-center">인스턴스가 없습니다</div>
      {:else}
        <!-- 테이블 헤더 (모바일: 2열, sm+: 4열) -->
        <div class="overflow-x-auto">
          <div class="min-w-[360px]">
            <div class="grid grid-cols-[1.7fr_100px_130px_0px] sm:grid-cols-[1.7fr_110px_130px_120px] px-3.5 py-2 bg-[#0B1220] rounded-t-[10px] border border-gray-800 border-b-0 text-[11px] uppercase tracking-wider text-gray-500 font-medium">
              <div>NAME</div>
              <div>STATUS</div>
              <div>IP</div>
              <div class="hidden sm:block">FLAVOR</div>
            </div>
            <div class="border border-gray-800 rounded-b-[10px] overflow-hidden">
              {#each recentInstances as inst, i}
                <a href="/dashboard/compute/instances"
                  class="grid grid-cols-[1.7fr_100px_130px_0px] sm:grid-cols-[1.7fr_110px_130px_120px] px-3.5 py-2.5 text-[13px] items-center hover:bg-gray-800/30 transition-colors {i < recentInstances.length - 1 ? 'border-b border-gray-800' : ''}">
                  <div class="text-white font-medium truncate">{inst.name}</div>
                  <div><StatusChip status={inst.status} /></div>
                  <div class="text-gray-300 font-mono text-xs">{getFirstIp(inst)}</div>
                  <div class="text-gray-400 text-xs truncate hidden sm:block">{inst.flavor_name ?? '—'}</div>
                </a>
              {/each}
            </div>
          </div>
        </div>
      {/if}
    </div>

    <!-- 쿼터 사용률 -->
    <div class="bg-gray-900 border border-gray-800 rounded-2xl p-5">
      <div class="text-white text-[15px] font-semibold mb-3.5">쿼터 사용률</div>
      {#if !quotas && !summary}
        <div class="space-y-4">
          {#each Array(5) as _}
            <div class="h-8 bg-gray-800 rounded animate-pulse"></div>
          {/each}
        </div>
      {:else}
        <div class="flex flex-col gap-3.5">
          {#if summary}
            <QuotaBar
              label="vCPU"
              used={summary.compute.vcpus_used}
              limit={summary.compute.vcpus_limit}
              color="bg-blue-500"
            />
            <QuotaBar
              label="Memory (GB)"
              used={Math.round(summary.compute.ram_used_mb / 1024)}
              limit={Math.round(summary.compute.ram_limit_mb / 1024)}
              color="bg-cyan-400"
            />
            <QuotaBar
              label="Storage (GB)"
              used={summary.storage.gigabytes_used}
              limit={summary.storage.gigabytes_limit}
              color="bg-violet-400"
            />
          {/if}
          {#if quotas}
            <QuotaBar
              label="Floating IP"
              used={quotas.network.floatingip.in_use}
              limit={quotas.network.floatingip.limit}
              color="bg-amber-400"
            />
            <QuotaBar
              label="Manila Shares"
              used={quotas.file_storage.shares.in_use}
              limit={quotas.file_storage.shares.limit}
              color="bg-teal-400"
            />
          {/if}
        </div>
      {/if}
    </div>
  </div>

</div>
