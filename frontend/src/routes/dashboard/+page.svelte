<script lang="ts">
  import { auth } from '$lib/stores/auth';
  import { api } from '$lib/api/client';
  import type { DashboardSummary } from '$lib/types/resources';
  import { formatNumber, formatStorage } from '$lib/utils/format';

  interface QuotaItem { limit: number; in_use: number; }
  interface Quotas {
    compute: { instances: QuotaItem; cores: QuotaItem; ram: QuotaItem; key_pairs: QuotaItem; server_groups: QuotaItem; };
    storage: { volumes: QuotaItem; snapshots: QuotaItem; gigabytes: QuotaItem; backups: QuotaItem; backup_gigabytes: QuotaItem; };
    network: { floatingip: QuotaItem; security_group: QuotaItem; security_group_rule: QuotaItem; network: QuotaItem; port: QuotaItem; router: QuotaItem; subnet: QuotaItem; };
    share: { shares: QuotaItem; gigabytes: QuotaItem; share_networks: QuotaItem; share_groups: QuotaItem; };
  }

  interface UsageServer { name: string; instance_id: string; vcpus: number; memory_mb: number; local_gb: number; hours: number; state: string; }
  interface Usage {
    start: string; end: string;
    total_vcpus_usage: number; total_memory_mb_usage: number; total_local_gb_usage: number; total_hours: number;
    server_usages: UsageServer[];
  }

  let summary = $state<DashboardSummary | null>(null);
  let quotas = $state<Quotas | null>(null);
  let usage = $state<Usage | null>(null);
  let usageLoading = $state(false);
  let refreshIntervalMs = $state(5000);

  // 사용량 날짜 범위
  const today = new Date();
  const defaultStart = new Date(today); defaultStart.setDate(today.getDate() - 30);
  let usageStart = $state(defaultStart.toISOString().slice(0, 10));
  let usageEnd = $state(today.toISOString().slice(0, 10));

  const token = $derived($auth.token ?? undefined);
  const projectId = $derived($auth.projectId ?? undefined);

  async function fetchSummary() {
    try {
      summary = await api.get<DashboardSummary>('/api/dashboard/summary', token, projectId);
    } catch { /* ignore */ }
  }

  async function fetchQuotas() {
    try {
      quotas = await api.get<Quotas>('/api/dashboard/quotas', token, projectId);
    } catch { /* ignore */ }
  }

  async function fetchUsage() {
    usageLoading = true;
    try {
      usage = await api.get<Usage>(`/api/dashboard/usage?start=${usageStart}&end=${usageEnd}`, token, projectId);
    } catch { /* ignore */ } finally { usageLoading = false; }
  }

  async function loadConfig() {
    try {
      const cfg = await api.get<{ refresh_interval_ms: number }>('/api/dashboard/config', token, projectId);
      refreshIntervalMs = cfg.refresh_interval_ms;
    } catch { /* ignore */ }
  }

  $effect(() => {
    const pid = $auth.projectId;
    if (!pid) return;
    loadConfig().then(() => { fetchSummary(); fetchQuotas(); fetchUsage(); });
    const interval = setInterval(fetchSummary, refreshIntervalMs);
    return () => clearInterval(interval);
  });

  function downloadCSV() {
    if (!usage?.server_usages.length) return;
    const header = '인스턴스,vCPUs,메모리(MB),디스크(GB),사용시간(h),상태';
    const rows = usage.server_usages.map(s =>
      `${s.name},${s.vcpus},${s.memory_mb},${s.local_gb},${s.hours.toFixed(2)},${s.state}`
    );
    const blob = new Blob([header + '\n' + rows.join('\n')], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `usage_${usageStart}_${usageEnd}.csv`; a.click();
    URL.revokeObjectURL(url);
  }
</script>

<div class="p-8">
  <h1 class="text-2xl font-bold text-white mb-6">대시보드</h1>

  <!-- 상단: 리소스 요약 카드 + 사용자 정보 -->
  <div class="flex gap-6 mb-8">
    <!-- 리소스 모니터링 카드 -->
    {#if summary}
      {@const c = summary.compute}
      {@const s = summary.storage}
      <div class="flex-1 grid grid-cols-2 gap-3 lg:grid-cols-3">
        <div class="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div class="text-xs text-gray-500 uppercase tracking-wide mb-2">인스턴스</div>
          <div class="text-2xl font-bold text-white mb-1">{formatNumber(summary.instances.active)}<span class="text-base text-gray-500">/{formatNumber(summary.instances.total)}</span></div>
          <div class="flex gap-2 text-xs">
            <span class="text-green-400">{formatNumber(summary.instances.active)} active</span>
            {#if summary.instances.shutoff > 0}<span class="text-gray-500">{formatNumber(summary.instances.shutoff)} off</span>{/if}
            {#if summary.instances.error > 0}<span class="text-red-400">{formatNumber(summary.instances.error)} err</span>{/if}
          </div>
        </div>
        <div class="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div class="text-xs text-gray-500 uppercase tracking-wide mb-2">vCPU</div>
          <div class="text-2xl font-bold text-white mb-1">{formatNumber(c.vcpus_used)}<span class="text-base text-gray-500">{c.vcpus_limit > 0 ? `/${formatNumber(c.vcpus_limit)}` : ''}</span></div>
          {#if c.vcpus_limit > 0}
            {@const pct = Math.round(c.vcpus_used / c.vcpus_limit * 100)}
            <div class="w-full bg-gray-800 rounded-full h-1.5">
              <div class="h-1.5 rounded-full {pct > 80 ? 'bg-red-500' : pct > 60 ? 'bg-yellow-500' : 'bg-blue-500'}" style="width:{pct}%"></div>
            </div>
          {/if}
        </div>
        <div class="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div class="text-xs text-gray-500 uppercase tracking-wide mb-2">RAM</div>
          <div class="text-2xl font-bold text-white mb-1">{formatStorage(Math.round(c.ram_used_mb / 1024))}<span class="text-base text-gray-500">{c.ram_limit_mb > 0 ? ` / ${formatStorage(Math.round(c.ram_limit_mb / 1024))}` : ''}</span></div>
          {#if c.ram_limit_mb > 0}
            {@const pct = Math.round(c.ram_used_mb / c.ram_limit_mb * 100)}
            <div class="w-full bg-gray-800 rounded-full h-1.5">
              <div class="h-1.5 rounded-full {pct > 80 ? 'bg-red-500' : pct > 60 ? 'bg-yellow-500' : 'bg-green-500'}" style="width:{pct}%"></div>
            </div>
          {/if}
        </div>
        <div class="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div class="text-xs text-gray-500 uppercase tracking-wide mb-2">GPU (활성)</div>
          <div class="text-2xl font-bold {summary.gpu_used > 0 ? 'text-purple-300' : 'text-white'} mb-1">{formatNumber(summary.gpu_used)}</div>
          <div class="text-xs text-gray-500">GPU 인스턴스</div>
        </div>
        <div class="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div class="text-xs text-gray-500 uppercase tracking-wide mb-2">볼륨</div>
          <div class="text-2xl font-bold text-white mb-1">{formatNumber(s.volumes_used)}<span class="text-base text-gray-500">{s.volumes_limit > 0 ? `/${formatNumber(s.volumes_limit)}` : ''}</span></div>
          {#if s.volumes_limit > 0}
            {@const pct = Math.round(s.volumes_used / s.volumes_limit * 100)}
            <div class="w-full bg-gray-800 rounded-full h-1.5">
              <div class="h-1.5 rounded-full {pct > 80 ? 'bg-red-500' : pct > 60 ? 'bg-yellow-500' : 'bg-cyan-500'}" style="width:{pct}%"></div>
            </div>
          {/if}
        </div>
        <div class="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <div class="text-xs text-gray-500 uppercase tracking-wide mb-2">볼륨 스토리지</div>
          <div class="text-2xl font-bold text-white mb-1">{formatStorage(s.gigabytes_used)}<span class="text-base text-gray-500">{s.gigabytes_limit > 0 ? ` / ${formatStorage(s.gigabytes_limit)}` : ''}</span></div>
          {#if s.gigabytes_limit > 0}
            {@const pct = Math.round(s.gigabytes_used / s.gigabytes_limit * 100)}
            <div class="w-full bg-gray-800 rounded-full h-1.5">
              <div class="h-1.5 rounded-full {pct > 80 ? 'bg-red-500' : pct > 60 ? 'bg-yellow-500' : 'bg-orange-500'}" style="width:{pct}%"></div>
            </div>
          {/if}
        </div>
        <!-- 네트워크 / Share 카드 (quotas 로드 후 표시) -->
        {#if quotas}
          {@const nq = quotas.network}
          {@const sq = quotas.share}
          <div class="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <div class="text-xs text-gray-500 uppercase tracking-wide mb-2">포트</div>
            <div class="text-2xl font-bold text-white mb-1">{formatNumber(nq.port.in_use)}<span class="text-base text-gray-500">{nq.port.limit > 0 ? `/${formatNumber(nq.port.limit)}` : ''}</span></div>
            {#if nq.port.limit > 0}
              {@const pct = Math.round(nq.port.in_use / nq.port.limit * 100)}
              <div class="w-full bg-gray-800 rounded-full h-1.5">
                <div class="h-1.5 rounded-full {pct > 80 ? 'bg-red-500' : pct > 60 ? 'bg-yellow-500' : 'bg-indigo-500'}" style="width:{pct}%"></div>
              </div>
            {/if}
          </div>
          <div class="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <div class="text-xs text-gray-500 uppercase tracking-wide mb-2">Floating IP</div>
            <div class="text-2xl font-bold text-white mb-1">{formatNumber(nq.floatingip.in_use)}<span class="text-base text-gray-500">{nq.floatingip.limit > 0 ? `/${formatNumber(nq.floatingip.limit)}` : ''}</span></div>
            {#if nq.floatingip.limit > 0}
              {@const pct = Math.round(nq.floatingip.in_use / nq.floatingip.limit * 100)}
              <div class="w-full bg-gray-800 rounded-full h-1.5">
                <div class="h-1.5 rounded-full {pct > 80 ? 'bg-red-500' : pct > 60 ? 'bg-yellow-500' : 'bg-sky-500'}" style="width:{pct}%"></div>
              </div>
            {/if}
          </div>
          <div class="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <div class="text-xs text-gray-500 uppercase tracking-wide mb-2">Share</div>
            <div class="text-2xl font-bold text-white mb-1">{formatNumber(sq.shares.in_use)}<span class="text-base text-gray-500">{sq.shares.limit > 0 ? `/${formatNumber(sq.shares.limit)}` : ''}</span></div>
            {#if sq.shares.limit > 0}
              {@const pct = Math.round(sq.shares.in_use / sq.shares.limit * 100)}
              <div class="w-full bg-gray-800 rounded-full h-1.5">
                <div class="h-1.5 rounded-full {pct > 80 ? 'bg-red-500' : pct > 60 ? 'bg-yellow-500' : 'bg-teal-500'}" style="width:{pct}%"></div>
              </div>
            {/if}
          </div>
          <div class="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <div class="text-xs text-gray-500 uppercase tracking-wide mb-2">Share 스토리지</div>
            <div class="text-2xl font-bold text-white mb-1">{formatStorage(sq.gigabytes.in_use)}<span class="text-base text-gray-500">{sq.gigabytes.limit > 0 ? ` / ${formatStorage(sq.gigabytes.limit)}` : ''}</span></div>
            {#if sq.gigabytes.limit > 0}
              {@const pct = Math.round(sq.gigabytes.in_use / sq.gigabytes.limit * 100)}
              <div class="w-full bg-gray-800 rounded-full h-1.5">
                <div class="h-1.5 rounded-full {pct > 80 ? 'bg-red-500' : pct > 60 ? 'bg-yellow-500' : 'bg-emerald-500'}" style="width:{pct}%"></div>
              </div>
            {/if}
          </div>
        {/if}
      </div>
    {:else}
      <div class="flex-1 grid grid-cols-3 gap-3">
        {#each Array(6) as _}
          <div class="bg-gray-900 border border-gray-800 rounded-lg p-4 animate-pulse h-24"></div>
        {/each}
      </div>
    {/if}

    <!-- 사용자 정보 카드 -->
    <div class="w-64 shrink-0 bg-gray-900 border border-gray-800 rounded-xl p-5">
      <div class="text-xs text-gray-500 uppercase tracking-wide mb-4">Hello, {$auth.username}</div>
      <div class="space-y-3 text-sm">
        <div class="flex items-start gap-2">
          <span class="text-gray-500 text-xs w-20 shrink-0 pt-0.5">사용자</span>
          <span class="text-white font-medium">{$auth.username}</span>
        </div>
        <div class="flex items-start gap-2">
          <span class="text-gray-500 text-xs w-20 shrink-0 pt-0.5">내 권한</span>
          <div class="flex flex-wrap gap-1">
            {#each ($auth.roles ?? []) as role}
              <span class="px-1.5 py-0.5 bg-blue-900/40 text-blue-300 text-xs rounded">{role}</span>
            {/each}
          </div>
        </div>
        <div class="flex items-start gap-2">
          <span class="text-gray-500 text-xs w-20 shrink-0 pt-0.5">프로젝트</span>
          <span class="text-gray-300 text-xs">{$auth.projectName ?? '-'}</span>
        </div>
      </div>
    </div>
  </div>

  <!-- 퀵 링크 -->
  <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
    <a href="/dashboard/compute/instances" class="bg-gray-900 border border-gray-800 hover:border-gray-600 rounded-xl p-4 transition-colors text-center">
      <div class="text-sm font-medium text-white mb-0.5">인스턴스</div>
      <div class="text-xs text-gray-500">VM 관리</div>
    </a>
    <a href="/dashboard/volumes" class="bg-gray-900 border border-gray-800 hover:border-gray-600 rounded-xl p-4 transition-colors text-center">
      <div class="text-sm font-medium text-white mb-0.5">볼륨</div>
      <div class="text-xs text-gray-500">블록 스토리지</div>
    </a>
    <a href="/dashboard/shares" class="bg-gray-900 border border-gray-800 hover:border-gray-600 rounded-xl p-4 transition-colors text-center">
      <div class="text-sm font-medium text-white mb-0.5">공유 스토리지</div>
      <div class="text-xs text-gray-500">Manila CephFS</div>
    </a>
    <a href="/dashboard/network/networks" class="bg-gray-900 border border-gray-800 hover:border-gray-600 rounded-xl p-4 transition-colors text-center">
      <div class="text-sm font-medium text-white mb-0.5">네트워크</div>
      <div class="text-xs text-gray-500">가상 네트워크</div>
    </a>
    <a href="/dashboard/network/topology" class="bg-gray-900 border border-gray-800 hover:border-gray-600 rounded-xl p-4 transition-colors text-center">
      <div class="text-sm font-medium text-white mb-0.5">토폴로지</div>
      <div class="text-xs text-gray-500">네트워크 시각화</div>
    </a>
    <a href="/create" class="bg-blue-900/40 border border-blue-800 hover:border-blue-600 rounded-xl p-4 transition-colors text-center">
      <div class="text-sm font-medium text-blue-300 mb-0.5">+ VM 생성</div>
      <div class="text-xs text-blue-500">새 인스턴스 배포</div>
    </a>
  </div>

  <!-- 사용량 요약 -->
  <div class="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-6">
    <div class="flex items-center gap-4 mb-4 flex-wrap">
      <h2 class="text-base font-semibold text-white">사용량 요약</h2>
      <div class="flex items-center gap-2 text-sm">
        <input bind:value={usageStart} type="date" class="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-gray-300 text-xs focus:outline-none focus:border-blue-500" />
        <span class="text-gray-500">~</span>
        <input bind:value={usageEnd} type="date" class="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-gray-300 text-xs focus:outline-none focus:border-blue-500" />
        <button onclick={fetchUsage} disabled={usageLoading} class="px-3 py-1 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 text-white text-xs rounded transition-colors">
          {usageLoading ? '조회 중...' : '조회'}
        </button>
      </div>
    </div>

    {#if usage}
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
        <div class="bg-gray-800/50 rounded-lg p-3">
          <div class="text-xs text-gray-500 mb-1">활성화된 인스턴스</div>
          <div class="text-xl font-bold text-white">{usage.server_usages.filter(s => s.state === 'active').length}</div>
        </div>
        <div class="bg-gray-800/50 rounded-lg p-3">
          <div class="text-xs text-gray-500 mb-1">vCPU 사용 시간</div>
          <div class="text-xl font-bold text-white">{formatNumber(Math.round(usage.total_vcpus_usage))}h</div>
        </div>
        <div class="bg-gray-800/50 rounded-lg p-3">
          <div class="text-xs text-gray-500 mb-1">RAM 사용 시간 (GiB·h)</div>
          <div class="text-xl font-bold text-white">{formatNumber(Math.round(usage.total_memory_mb_usage / 1024))}</div>
        </div>
        <div class="bg-gray-800/50 rounded-lg p-3">
          <div class="text-xs text-gray-500 mb-1">디스크 사용 시간 (GB·h)</div>
          <div class="text-xl font-bold text-white">{formatNumber(Math.round(usage.total_local_gb_usage))}</div>
        </div>
      </div>

      {#if usage.server_usages.length > 0}
        <div class="flex items-center justify-between mb-2">
          <div class="text-sm text-gray-400">{usage.server_usages.length}개 인스턴스</div>
          <button onclick={downloadCSV} class="text-xs text-blue-400 hover:text-blue-300 transition-colors border border-blue-800 hover:border-blue-600 px-2.5 py-1 rounded">
            CSV 다운로드
          </button>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
                <th class="text-left py-2 pr-4">인스턴스 이름</th>
                <th class="text-left py-2 pr-4">vCPUs</th>
                <th class="text-left py-2 pr-4">디스크</th>
                <th class="text-left py-2 pr-4">RAM</th>
                <th class="text-left py-2 pr-4">기간(Age)</th>
                <th class="text-left py-2">상태</th>
              </tr>
            </thead>
            <tbody>
              {#each usage.server_usages as s}
                <tr class="border-b border-gray-800/50 text-xs">
                  <td class="py-2 pr-4 text-white">{s.name}</td>
                  <td class="py-2 pr-4 text-gray-400">{formatNumber(s.vcpus)}</td>
                  <td class="py-2 pr-4 text-gray-400">{formatStorage(s.local_gb)}</td>
                  <td class="py-2 pr-4 text-gray-400">{formatStorage(Math.round(s.memory_mb / 1024))}</td>
                  <td class="py-2 pr-4 text-gray-400">
                    {s.hours >= 720 ? `${Math.floor(s.hours/720)}개월 ${Math.floor((s.hours%720)/24)}일` :
                     s.hours >= 24 ? `${Math.floor(s.hours/24)}일` : `${Math.round(s.hours)}시간`}
                  </td>
                  <td class="py-2 {s.state === 'active' ? 'text-green-400' : 'text-gray-500'}">{s.state}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {:else}
        <div class="text-gray-600 text-sm">선택한 기간에 사용량이 없습니다</div>
      {/if}
    {:else if usageLoading}
      <div class="text-gray-500 text-sm">로딩 중...</div>
    {/if}
  </div>

</div>
