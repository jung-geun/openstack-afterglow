<script lang="ts">
  import { auth } from '$lib/stores/auth';
  import { untrack } from 'svelte';
  import { api, ApiError, memoryCache } from '$lib/api/client';
  import type { Network, FloatingIp } from '$lib/types/resources';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
  import RefreshButton from '$lib/components/RefreshButton.svelte';
  import AutoRefreshToggle from '$lib/components/AutoRefreshToggle.svelte';
  import SlidePanel from '$lib/components/SlidePanel.svelte';
  import NetworkDetailPanel from '$lib/components/NetworkDetailPanel.svelte';
  import StatusChip from '$lib/components/ui/StatusChip.svelte';
  import PageHeader from '$lib/components/ui/PageHeader.svelte';


  let networks = $state<Network[]>([]);
  let floatingIps = $state<FloatingIp[]>([]);
  let loading = $state(true);
  let refreshing = $state(false);
  let error = $state('');
  let autoRefresh = $state(false);
  let deleting = $state<string | null>(null);
  let selectedNetworkId = $state<string | null>(null);

  function openNetworkPanel(id: string) {
    selectedNetworkId = id;
    history.pushState({ networkId: id }, '', `/dashboard/network/networks/${id}`);
  }
  function closeNetworkPanel() {
    selectedNetworkId = null;
    history.pushState({}, '', '/dashboard/network/networks');
  }

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

  async function fetchNetworks(opts?: { refresh?: boolean }) {
    const path = '/api/networks';
    const cached = swrGet<Network[]>(path);
    if (cached && networks.length === 0) networks = cached;
    try {
      networks = await api.get<Network[]>(path, $auth.token ?? undefined, $auth.projectId ?? undefined, opts);
      swrSet(path, networks);
      error = '';
    } catch (e) {
      if (!cached) error = e instanceof ApiError ? `조회 실패 (${e.status})` : '서버 오류';
    } finally {
      loading = false;
    }
  }

  async function fetchFloatingIps() {
    try {
      floatingIps = await api.get<FloatingIp[]>('/api/networks/floating-ips', $auth.token ?? undefined, $auth.projectId ?? undefined);
    } catch { /* 오류 무시 */ }
  }

  async function forceRefresh() {
    refreshing = true;
    try {
      await Promise.all([fetchNetworks({ refresh: true }), fetchFloatingIps()]);
    } finally {
      refreshing = false;
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
    untrack(() => { fetchNetworks(); fetchFloatingIps(); });
  });

  $effect(() => {
    if (!$auth.projectId || !autoRefresh) return;
    const interval = setInterval(() => untrack(() => { fetchNetworks(); fetchFloatingIps(); }), 30000);
    return () => clearInterval(interval);
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

<div class="p-4 md:p-8">
  <PageHeader breadcrumb="NETWORK / NETWORKS" title="네트워크">
    {#snippet actions()}
      <AutoRefreshToggle bind:active={autoRefresh} intervalSeconds={30} />
      <RefreshButton {refreshing} onclick={forceRefresh} />
      <button onclick={() => showModal = true} class="bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">+ 네트워크 생성</button>
    {/snippet}
  </PageHeader>

  {#if error}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>{/if}

  {#if loading}
    <LoadingSkeleton variant="table" rows={5} />
  {:else if networks.length === 0}
    <div class="text-center py-20 text-gray-600">
      <div class="text-5xl mb-4">🌐</div>
      <p class="text-lg">네트워크가 없습니다</p>
    </div>
  {:else}
    <div class="flex flex-col gap-4">
      <!-- Networks card -->
      <div class="bg-gray-900 border border-gray-800 rounded-2xl p-5">
        <div class="text-white text-[15px] font-semibold mb-3.5">네트워크</div>
        <div class="bg-[#0B1220] border border-gray-800 rounded-[10px] overflow-hidden">
          <!-- Header -->
          <div class="grid grid-cols-[1.4fr_1fr_110px_90px_90px_110px_auto] px-4 py-2.5 border-b border-gray-800 text-[11px] uppercase tracking-wider text-gray-500 font-medium">
            <div>이름</div>
            <div>CIDR</div>
            <div>유형</div>
            <div>서브넷</div>
            <div>MTU</div>
            <div>상태</div>
            <div></div>
          </div>
          <!-- Rows -->
          {#each networks as net (net.id)}
            <div
              onclick={() => openNetworkPanel(net.id)}
              onkeydown={(e) => e.key === 'Enter' && openNetworkPanel(net.id)}
              tabindex="0"
              role="button"
              class="grid grid-cols-[1.4fr_1fr_110px_90px_90px_110px_auto] px-4 py-3 text-[13px] items-center border-b border-gray-800 hover:bg-gray-800/30 transition-colors cursor-pointer last:border-b-0"
            >
              <!-- 이름 -->
              <div class="flex items-center gap-2.5 min-w-0">
                <div class="shrink-0 w-7 h-7 rounded-md bg-violet-500/15 border border-violet-500/30 flex items-center justify-center">
                  <svg class="w-3.5 h-3.5 text-violet-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <div class="min-w-0">
                  <div class="text-white font-medium truncate">{net.name || net.id.slice(0, 12)}</div>
                  <div class="text-[11px] text-gray-500 font-mono truncate">{net.id.slice(0, 8)}…</div>
                </div>
              </div>
              <!-- CIDR -->
              <div class="text-gray-400 font-mono text-[12px]">—</div>
              <!-- 유형 badge -->
              <div>
                {#if net.is_external}
                  <span class="text-[11px] px-2 py-0.5 rounded-md bg-amber-900/25 border border-amber-800 text-amber-400">외부</span>
                {:else if net.is_shared}
                  <span class="text-[11px] px-2 py-0.5 rounded-md bg-teal-500/15 border border-teal-500/30 text-teal-400">공유</span>
                {:else}
                  <span class="text-[11px] px-2 py-0.5 rounded-md bg-gray-800 border border-gray-700 text-gray-300">내부</span>
                {/if}
              </div>
              <!-- 서브넷 -->
              <div class="text-gray-400 text-[12px]">{net.subnets.length}개</div>
              <!-- MTU -->
              <div class="text-gray-500 font-mono text-[12px]">—</div>
              <!-- 상태 -->
              <div><StatusChip status={net.status} /></div>
              <!-- 액션 -->
              <div onclick={(e) => e.stopPropagation()} role="none">
                {#if !net.is_external && !net.is_shared}
                  <button
                    onclick={(e) => { e.stopPropagation(); deleteNetwork(net.id, net.name, net.is_external, net.is_shared); }}
                    disabled={deleting === net.id}
                    class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-1 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors"
                  >{deleting === net.id ? '삭제 중...' : '삭제'}</button>
                {/if}
              </div>
            </div>
          {/each}
        </div>
      </div>

      <!-- Floating IP card -->
      <div class="bg-gray-900 border border-gray-800 rounded-2xl p-5">
        <div class="flex items-center mb-3.5">
          <div class="text-white text-[15px] font-semibold">Floating IP</div>
          <div class="ml-auto flex gap-2">
            <button class="px-3 py-1.5 text-[13px] text-gray-300 hover:text-white border border-gray-700 hover:border-gray-500 rounded-lg transition-colors">할당</button>
            <button class="px-3 py-1.5 text-[13px] bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-lg transition-colors">IP 예약</button>
          </div>
        </div>
        {#if floatingIps.length === 0}
          <div class="text-center py-8 text-gray-600 text-sm">Floating IP가 없습니다</div>
        {:else}
          <div class="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
            {#each floatingIps as fip (fip.id)}
              <div class="bg-[#0B1220] border border-gray-800 rounded-lg p-3 flex items-center gap-3">
                <div class="flex-1 min-w-0">
                  <div class="font-mono text-[13px] text-white">{fip.floating_ip_address}</div>
                  <div class="text-[11px] text-gray-500 mt-0.5 truncate">
                    {fip.fixed_ip_address ? '→ ' + fip.fixed_ip_address : '미할당'}
                  </div>
                </div>
                <StatusChip status={fip.status} />
              </div>
            {/each}
          </div>
        {/if}
      </div>
    </div>
  {/if}
</div>

{#if selectedNetworkId}
  <SlidePanel onClose={closeNetworkPanel} width="w-full md:w-[60vw] max-w-2xl">
    <NetworkDetailPanel
      networkId={selectedNetworkId}
      apiBase="/api/networks"
      onClose={closeNetworkPanel}
      token={$auth.token ?? undefined}
      projectId={$auth.projectId ?? undefined}
    />
  </SlidePanel>
{/if}
