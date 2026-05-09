<script lang="ts">
  import { untrack } from 'svelte';
  import { auth } from '$lib/stores/auth';
  import { api, ApiError, memoryCache } from '$lib/api/client';
  import { apiMut } from '$lib/api/mutations';
  import { goto } from '$app/navigation';
  import type { Instance } from '$lib/types/resources';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
  import InstanceDetailPanel from '$lib/components/InstanceDetailPanel.svelte';
  import SlidePanel from '$lib/components/SlidePanel.svelte';
  import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
  import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
  import StatusChip from '$lib/components/ui/StatusChip.svelte';
  import PageHeader from '$lib/components/ui/PageHeader.svelte';
  import ActionMenu from '$lib/components/ui/ActionMenu.svelte';
  import { openWizard } from '$lib/stores/wizard';

  const strategyLabel: Record<string, string> = { prebuilt: '사전 빌드', dynamic: '동적 생성' };

  let instances = $state<Instance[]>([]);
  let loading = $state(true);
  let refreshing = $state(false);
  let error = $state('');
  let deleting = $state<string | null>(null);
  let selectedInstanceId = $state<string | null>(null);
  let openMenuId = $state<string | null>(null);

  function swrGet<T>(path: string): T | null {
    const key = `${path}:${$auth.projectId}`;
    const c = memoryCache.get(key);
    return c ? (c.data as T) : null;
  }
  function swrSet(path: string, data: unknown) {
    memoryCache.set(`${path}:${$auth.projectId}`, { data, timestamp: Date.now() });
  }

  async function fetchInstances(opts?: { refresh?: boolean }) {
    const path = '/api/instances';
    const cached = swrGet<Instance[]>(path);
    if (cached && instances.length === 0) instances = cached;
    try {
      instances = await api.get<Instance[]>(path, $auth.token ?? undefined, $auth.projectId ?? undefined, opts);
      swrSet(path, instances);
      error = '';
    } catch (e) {
      if (!cached) error = e instanceof ApiError ? `조회 실패 (${e.status}): ${(e as ApiError).message}` : '서버 오류';
    } finally {
      loading = false;
    }
  }

  async function forceRefresh() {
    refreshing = true;
    try {
      await fetchInstances({ refresh: true });
    } finally {
      refreshing = false;
    }
  }

  const ar = createAutoRefresh(() => fetchInstances(), {
    storageKey: 'dashboard-compute-instances',
    defaultActive: true,
    defaultInterval: 10,
    intervalOptions: [10, 15, 30, 60],
  });

  async function shelveInstance(id: string) {
    if (!confirm('인스턴스를 보관하시겠습니까? (SHELVED_OFFLOADED 상태로 전환됩니다)')) return;
    try {
      await apiMut('인스턴스 보관', () => api.post(`/api/instances/${id}/shelve`, {}, $auth.token ?? undefined, $auth.projectId ?? undefined));
      await fetchInstances();
    } catch {
      // error toast shown by apiMut
    }
  }

  async function unshelveInstance(id: string) {
    if (!confirm('인스턴스 보관을 해제하시겠습니까?')) return;
    try {
      await apiMut('인스턴스 보관 해제', () => api.post(`/api/instances/${id}/unshelve`, {}, $auth.token ?? undefined, $auth.projectId ?? undefined));
      await fetchInstances();
    } catch {
      // error toast shown by apiMut
    }
  }

  async function deleteInstance(id: string, name: string) {
    if (!confirm(`"${name}" 인스턴스를 삭제하시겠습니까?\nManila share와 볼륨도 함께 삭제됩니다.`)) return;
    deleting = id;
    try {
      await apiMut('인스턴스 삭제', () => api.delete(`/api/instances/${id}`, $auth.token ?? undefined, $auth.projectId ?? undefined));
      await fetchInstances();
    } catch {
      // error toast shown by apiMut
    } finally {
      deleting = null;
    }
  }

  async function openConsole(id: string) {
    try {
      const data = await api.get<{ url: string }>(`/api/instances/${id}/console`, $auth.token ?? undefined, $auth.projectId ?? undefined);
      window.open(data.url, '_blank');
    } catch {
      alert('콘솔 URL을 가져올 수 없습니다');
    }
  }

  function openInstancePanel(id: string) {
    selectedInstanceId = id;
    history.pushState({ instanceId: id }, '', `/dashboard/compute/instances/${id}`);
  }

  function closeInstancePanel() {
    selectedInstanceId = null;
    history.pushState({}, '', '/dashboard/compute/instances');
  }

  $effect(() => {
    const projectId = $auth.projectId;
    if (!projectId) return;
    loading = true;
    untrack(() => fetchInstances());
  });
</script>

<div class="p-4 md:p-8">
  <PageHeader breadcrumb="COMPUTE / INSTANCES" title="인스턴스">
    {#snippet actions()}
      <AutoRefreshControl
        bind:active={ar.active}
        bind:intervalSeconds={ar.intervalSeconds}
        intervalOptions={ar.intervalOptions}
        refreshing={refreshing}
        onManualRefresh={forceRefresh}
      />
      <button type="button" onclick={openWizard} class="bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
        + VM 생성
      </button>
    {/snippet}
  </PageHeader>

  {#if error}
    <div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>
  {/if}

  {#if loading}
    <LoadingSkeleton variant="table" rows={5} />
  {:else if instances.length === 0}
    <div class="text-center py-20 text-gray-600">
      <div class="text-5xl mb-4">☁️</div>
      <p class="text-lg">인스턴스가 없습니다</p>
      <button type="button" onclick={openWizard} class="text-blue-400 hover:text-blue-300 text-sm mt-2 inline-block bg-transparent">첫 VM을 생성하세요 →</button>
    </div>
  {:else}
    <div class="overflow-x-auto">
      <div class="bg-[#0B1220] border border-gray-800 rounded-[10px] overflow-hidden">
        <!-- 헤더 -->
        <div class="grid grid-cols-[1fr_0px_0px_1fr_0px_0px_0px] sm:grid-cols-[1.2fr_130px_0px_1.5fr_0px_0px_32px] md:grid-cols-[1.2fr_130px_1.2fr_1.5fr_0px_0px_32px] lg:grid-cols-[1.2fr_130px_1.2fr_1.5fr_80px_80px_32px] px-4 py-2.5 border-b border-gray-800 text-[11px] uppercase tracking-wider text-gray-500 font-medium">
          <div>이름</div>
          <div class="hidden sm:block">상태</div>
          <div class="hidden md:block">이미지 / 플레이버</div>
          <div>IP</div>
          <div class="hidden lg:block">라이브러리</div>
          <div class="hidden lg:block">전략</div>
          <div></div>
        </div>
        <!-- 행 -->
        {#each instances as inst (inst.id)}
          <div
            onclick={() => openInstancePanel(inst.id)}
            onkeydown={(e) => e.key === 'Enter' && openInstancePanel(inst.id)}
            tabindex="0"
            role="button"
            class="grid grid-cols-[1fr_0px_0px_1fr_0px_0px_0px] sm:grid-cols-[1.2fr_130px_0px_1.5fr_0px_0px_32px] md:grid-cols-[1.2fr_130px_1.2fr_1.5fr_0px_0px_32px] lg:grid-cols-[1.2fr_130px_1.2fr_1.5fr_80px_80px_32px] px-4 py-3 text-[13px] items-center border-b border-gray-800 hover:bg-gray-800/30 transition-colors cursor-pointer last:border-b-0"
          >
            <!-- 이름 -->
            <div class="flex items-center gap-2.5 min-w-0">
              <div class="shrink-0 w-7 h-7 rounded-md bg-blue-500/15 border border-blue-500/30 flex items-center justify-center">
                <svg class="w-3.5 h-3.5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2"/>
                </svg>
              </div>
              <div class="min-w-0">
                <div class="text-white font-medium truncate">{inst.name}</div>
                <div class="sm:hidden mt-0.5"><StatusChip status={inst.status} /></div>
              </div>
            </div>
            <!-- 상태 -->
            <div class="hidden sm:block overflow-hidden px-1"><StatusChip status={inst.status} class="max-w-full truncate" /></div>
            <!-- 이미지/플레이버 -->
            <div class="hidden md:block text-xs min-w-0">
              <div class="text-gray-300 truncate">{inst.image_name ?? '볼륨에서 부팅'}</div>
              {#if inst.flavor_name}<div class="text-gray-500 mt-0.5 truncate">{inst.flavor_name}</div>{/if}
            </div>
            <!-- IP -->
            <div class="text-[11px] sm:text-xs">
              {#if inst.ip_addresses.length > 0}
                {@const fixedIps = inst.ip_addresses.filter(ip => ip.type === 'fixed')}
                {@const floatingIps = inst.ip_addresses.filter(ip => ip.type === 'floating')}
                <div class="flex flex-col gap-0.5">
                  {#each fixedIps as fip}
                    {@const paired = floatingIps.find(fl => fl.network_name === fip.network_name)}
                    <div class="flex items-center gap-1 flex-wrap">
                      <span class="font-mono text-gray-400 whitespace-nowrap">{fip.addr}</span>
                      {#if paired}<span class="font-mono text-green-400 bg-green-900/20 px-1.5 py-0.5 rounded whitespace-nowrap">{paired.addr}</span>{/if}
                    </div>
                  {/each}
                </div>
              {:else}
                <span class="text-gray-600">-</span>
              {/if}
            </div>
            <!-- 라이브러리 -->
            <div class="hidden lg:flex flex-wrap gap-1">
              {#each inst.union_libraries.filter(Boolean) as lib}
                <span class="px-1.5 py-0.5 bg-blue-900/40 text-blue-300 rounded text-xs">{lib}</span>
              {/each}
            </div>
            <!-- 전략 -->
            <div class="hidden lg:block text-gray-500 text-xs">{inst.union_strategy ? strategyLabel[inst.union_strategy] ?? inst.union_strategy : '—'}</div>
            <!-- 액션 -->
            <div class="hidden sm:flex items-center justify-end" role="none">
              <ActionMenu
                open={openMenuId === inst.id}
                onopen={() => { openMenuId = inst.id; }}
                onclose={() => { openMenuId = null; }}
              >
                {#if inst.status === 'ACTIVE'}
                  <button onclick={() => { openMenuId = null; openConsole(inst.id); }} class="w-full text-left px-3 py-1.5 text-xs text-gray-300 hover:bg-gray-800 hover:text-white transition-colors">콘솔</button>
                {/if}
                {#if inst.status === 'ACTIVE' || inst.status === 'SHUTOFF'}
                  <button onclick={() => { openMenuId = null; shelveInstance(inst.id); }} class="w-full text-left px-3 py-1.5 text-xs text-purple-400 hover:bg-gray-800 hover:text-purple-300 transition-colors">보관</button>
                {/if}
                {#if inst.status === 'SHELVED_OFFLOADED' || inst.status === 'SHELVED'}
                  <button onclick={() => { openMenuId = null; unshelveInstance(inst.id); }} class="w-full text-left px-3 py-1.5 text-xs text-green-400 hover:bg-gray-800 hover:text-green-300 transition-colors">해제</button>
                {/if}
                <button onclick={() => { openMenuId = null; deleteInstance(inst.id, inst.name); }} disabled={deleting === inst.id} class="w-full text-left px-3 py-1.5 text-xs text-red-400 hover:bg-gray-800 hover:text-red-300 disabled:text-gray-600 transition-colors">
                  {deleting === inst.id ? '삭제 중...' : '삭제'}
                </button>
              </ActionMenu>
            </div>
          </div>
        {/each}
      </div>
    </div>
  {/if}
</div>

{#if selectedInstanceId}
  <SlidePanel onClose={closeInstancePanel}>
    <InstanceDetailPanel instanceId={selectedInstanceId} onClose={closeInstancePanel} />
  </SlidePanel>
{/if}
