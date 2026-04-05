<script lang="ts">
  import { auth } from '$lib/stores/auth';
  import { api } from '$lib/api/client';
  import type { DashboardSummary } from '$lib/types/resources';

  let summary = $state<DashboardSummary | null>(null);
  let refreshIntervalMs = $state(5000);

  async function fetchSummary() {
    try {
      summary = await api.get<DashboardSummary>('/api/dashboard/summary', $auth.token ?? undefined, $auth.projectId ?? undefined);
    } catch {
      // ignore
    }
  }

  async function loadConfig() {
    try {
      const cfg = await api.get<{ refresh_interval_ms: number }>('/api/dashboard/config', $auth.token ?? undefined, $auth.projectId ?? undefined);
      refreshIntervalMs = cfg.refresh_interval_ms;
    } catch {
      // ignore
    }
  }

  $effect(() => {
    const projectId = $auth.projectId;
    if (!projectId) return;
    loadConfig().then(() => {
      fetchSummary();
      const interval = setInterval(fetchSummary, refreshIntervalMs);
      return () => clearInterval(interval);
    });
  });
</script>

<div class="p-8">
  <h1 class="text-2xl font-bold text-white mb-6">대시보드</h1>

  <!-- 리소스 모니터링 카드 -->
  {#if summary}
    {@const c = summary.compute}
    {@const s = summary.storage}
    <div class="grid grid-cols-2 gap-3 mb-8 lg:grid-cols-6">
      <div class="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <div class="text-xs text-gray-500 uppercase tracking-wide mb-2">인스턴스</div>
        <div class="text-2xl font-bold text-white mb-1">{summary.instances.active}<span class="text-base text-gray-500">/{summary.instances.total}</span></div>
        <div class="flex gap-2 text-xs">
          <span class="text-green-400">{summary.instances.active} active</span>
          {#if summary.instances.shutoff > 0}<span class="text-gray-500">{summary.instances.shutoff} off</span>{/if}
          {#if summary.instances.error > 0}<span class="text-red-400">{summary.instances.error} err</span>{/if}
        </div>
      </div>
      <div class="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <div class="text-xs text-gray-500 uppercase tracking-wide mb-2">vCPU</div>
        <div class="text-2xl font-bold text-white mb-1">{c.vcpus_used}<span class="text-base text-gray-500">{c.vcpus_limit > 0 ? `/${c.vcpus_limit}` : ''}</span></div>
        {#if c.vcpus_limit > 0}
          {@const pct = Math.round(c.vcpus_used / c.vcpus_limit * 100)}
          <div class="w-full bg-gray-800 rounded-full h-1.5">
            <div class="h-1.5 rounded-full {pct > 80 ? 'bg-red-500' : pct > 60 ? 'bg-yellow-500' : 'bg-blue-500'}" style="width:{pct}%"></div>
          </div>
          <div class="text-xs text-gray-500 mt-1">{pct}% 사용</div>
        {/if}
      </div>
      <div class="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <div class="text-xs text-gray-500 uppercase tracking-wide mb-2">RAM</div>
        <div class="text-2xl font-bold text-white mb-1">{Math.round(c.ram_used_mb / 1024)}GB<span class="text-base text-gray-500">{c.ram_limit_mb > 0 ? `/${Math.round(c.ram_limit_mb / 1024)}GB` : ''}</span></div>
        {#if c.ram_limit_mb > 0}
          {@const pct = Math.round(c.ram_used_mb / c.ram_limit_mb * 100)}
          <div class="w-full bg-gray-800 rounded-full h-1.5">
            <div class="h-1.5 rounded-full {pct > 80 ? 'bg-red-500' : pct > 60 ? 'bg-yellow-500' : 'bg-green-500'}" style="width:{pct}%"></div>
          </div>
          <div class="text-xs text-gray-500 mt-1">{pct}% 사용</div>
        {/if}
      </div>
      <div class="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <div class="text-xs text-gray-500 uppercase tracking-wide mb-2">GPU (활성)</div>
        <div class="text-2xl font-bold {summary.gpu_used > 0 ? 'text-purple-300' : 'text-white'} mb-1">{summary.gpu_used}</div>
        <div class="text-xs text-gray-500">GPU 사용 인스턴스</div>
      </div>
      <div class="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <div class="text-xs text-gray-500 uppercase tracking-wide mb-2">볼륨</div>
        <div class="text-2xl font-bold text-white mb-1">{s.volumes_used}<span class="text-base text-gray-500">{s.volumes_limit > 0 ? `/${s.volumes_limit}` : ''}</span></div>
        {#if s.volumes_limit > 0}
          {@const pct = Math.round(s.volumes_used / s.volumes_limit * 100)}
          <div class="w-full bg-gray-800 rounded-full h-1.5">
            <div class="h-1.5 rounded-full {pct > 80 ? 'bg-red-500' : pct > 60 ? 'bg-yellow-500' : 'bg-cyan-500'}" style="width:{pct}%"></div>
          </div>
          <div class="text-xs text-gray-500 mt-1">{pct}% 사용</div>
        {:else}
          <div class="text-xs text-gray-500">볼륨 수</div>
        {/if}
      </div>
      <div class="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <div class="text-xs text-gray-500 uppercase tracking-wide mb-2">볼륨 스토리지</div>
        <div class="text-2xl font-bold text-white mb-1">{s.gigabytes_used}GB<span class="text-base text-gray-500">{s.gigabytes_limit > 0 ? `/${s.gigabytes_limit}GB` : ''}</span></div>
        {#if s.gigabytes_limit > 0}
          {@const pct = Math.round(s.gigabytes_used / s.gigabytes_limit * 100)}
          <div class="w-full bg-gray-800 rounded-full h-1.5">
            <div class="h-1.5 rounded-full {pct > 80 ? 'bg-red-500' : pct > 60 ? 'bg-yellow-500' : 'bg-orange-500'}" style="width:{pct}%"></div>
          </div>
          <div class="text-xs text-gray-500 mt-1">{s.volumes_used} 볼륨 / {pct}%</div>
        {:else}
          <div class="text-xs text-gray-500">{s.volumes_used} 볼륨</div>
        {/if}
      </div>
    </div>
  {/if}

  <!-- 퀵 링크 -->
  <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
    <a href="/dashboard/compute/instances" class="bg-gray-900 border border-gray-800 hover:border-gray-600 rounded-xl p-5 transition-colors">
      <div class="text-sm font-medium text-white mb-1">인스턴스</div>
      <div class="text-xs text-gray-500">VM 목록 및 관리</div>
    </a>
    <a href="/dashboard/volumes" class="bg-gray-900 border border-gray-800 hover:border-gray-600 rounded-xl p-5 transition-colors">
      <div class="text-sm font-medium text-white mb-1">볼륨</div>
      <div class="text-xs text-gray-500">블록 스토리지</div>
    </a>
    <a href="/dashboard/shares" class="bg-gray-900 border border-gray-800 hover:border-gray-600 rounded-xl p-5 transition-colors">
      <div class="text-sm font-medium text-white mb-1">공유 스토리지</div>
      <div class="text-xs text-gray-500">Manila CephFS 공유</div>
    </a>
    <a href="/dashboard/network/networks" class="bg-gray-900 border border-gray-800 hover:border-gray-600 rounded-xl p-5 transition-colors">
      <div class="text-sm font-medium text-white mb-1">네트워크</div>
      <div class="text-xs text-gray-500">가상 네트워크 관리</div>
    </a>
    <a href="/dashboard/network/topology" class="bg-gray-900 border border-gray-800 hover:border-gray-600 rounded-xl p-5 transition-colors">
      <div class="text-sm font-medium text-white mb-1">토폴로지</div>
      <div class="text-xs text-gray-500">네트워크 시각화</div>
    </a>
    <a href="/create" class="bg-blue-900/40 border border-blue-800 hover:border-blue-600 rounded-xl p-5 transition-colors">
      <div class="text-sm font-medium text-blue-300 mb-1">+ VM 생성</div>
      <div class="text-xs text-blue-500">새 인스턴스 배포</div>
    </a>
  </div>
</div>
