<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { untrack } from 'svelte';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import RefreshButton from '$lib/components/RefreshButton.svelte';
	import AutoRefreshToggle from '$lib/components/AutoRefreshToggle.svelte';
	import GlobalTopology from '$lib/components/GlobalTopology.svelte';
	import InstanceDetailPanel from '$lib/components/InstanceDetailPanel.svelte';
	import RouterDetailPanel from '$lib/components/RouterDetailPanel.svelte';
	import SlidePanel from '$lib/components/SlidePanel.svelte';

	let isLight = $state(false);
	$effect(() => {
		isLight = document.documentElement.classList.contains('light');
		const obs = new MutationObserver(() => {
			isLight = document.documentElement.classList.contains('light');
		});
		obs.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
		return () => obs.disconnect();
	});

	interface SubnetDetail {
		id: string; name: string; cidr: string;
		gateway_ip: string | null; dhcp_enabled: boolean;
	}
	interface TopologyNetwork {
		id: string; name: string; status: string;
		is_external: boolean; is_shared: boolean;
		project_id: string | null;
		subnet_details: SubnetDetail[];
	}
	interface TopologyRouter {
		id: string; name: string; status: string;
		external_gateway_network_id: string | null;
		connected_subnet_ids: string[];
		project_id: string | null;
	}
	interface TopologyInstance {
		id: string; name: string; status: string;
		network_names: string[];
		ip_addresses: { addr: string; type: string; network_name: string }[];
	}
	interface FloatingIpInfo {
		id: string; floating_ip_address: string;
		fixed_ip_address: string | null; status: string;
		port_id: string | null; floating_network_id: string;
		project_id?: string | null;
	}
	interface TopologyData {
		networks: TopologyNetwork[];
		routers: TopologyRouter[];
		instances: TopologyInstance[];
		floating_ips: FloatingIpInfo[];
	}

	let data = $state<TopologyData | null>(null);
	let loading = $state(true);
	let refreshing = $state(false);
	let error = $state('');
	let selectedInstanceId = $state<string | null>(null);
	let selectedRouterId = $state<string | null>(null);
	let autoRefresh = $state(false);

	$effect(() => {
		if (!$auth.token || !$auth.projectId) return;
		untrack(() => { fetchTopology(); });
	});

	$effect(() => {
		if (!$auth.projectId || !autoRefresh) return;
		const interval = setInterval(() => untrack(() => { fetchTopology(); }), 30000);
		return () => clearInterval(interval);
	});

	async function fetchTopology(opts?: { refresh?: boolean }) {
		loading = true;
		error = '';
		try {
			data = await api.get<TopologyData>(
				'/api/networks/topology',
				$auth.token ?? undefined,
				$auth.projectId ?? undefined,
				opts,
			);
		} catch (e) {
			error = e instanceof ApiError ? `조회 실패 (${e.status}): ${e.message}` : '서버 오류';
		} finally {
			loading = false;
		}
	}

	async function forceRefresh() {
		refreshing = true;
		try {
			await fetchTopology({ refresh: true });
		} finally {
			refreshing = false;
		}
	}
</script>

<div class="p-4 md:p-8 max-w-screen-2xl mx-auto">
	<div class="mb-6 flex items-center justify-between">
		<h1 class="text-2xl font-bold text-white">네트워크 토폴로지</h1>
		<div class="flex items-center gap-2">
			<AutoRefreshToggle bind:active={autoRefresh} intervalSeconds={30} />
			<RefreshButton refreshing={refreshing || loading} onclick={forceRefresh} />
		</div>
	</div>

	{#if error}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">
			{error}
		</div>
	{:else if loading}
		<LoadingSkeleton variant="card" rows={8} />
	{:else if data}
		<div class="bg-gray-900 border border-gray-800 rounded-lg p-6 mb-4">
			<GlobalTopology
				{data}
				projectId={$auth.projectId}
				onSelectInstance={(id) => { selectedInstanceId = id; }}
				onSelectRouter={(id) => { selectedRouterId = id; }}
			/>
		</div>

		<!-- 범례 -->
		<div class="flex flex-wrap gap-5 text-xs text-gray-400 px-1">
			<span class="flex items-center gap-1.5">
				<span class="inline-block w-2 h-4 rounded" style="background:#ea580c"></span>
				외부 네트워크
			</span>
			<span class="flex items-center gap-1.5">
				<span class="inline-block w-2 h-4 rounded" style="background:#0d9488"></span>
				공유 네트워크
			</span>
			<span class="flex items-center gap-1.5">
				<span class="inline-block w-2 h-4 rounded" style="background:#3b82f6"></span>
				내부 네트워크
			</span>
			<span class="flex items-center gap-1.5">
				<span class="inline-block w-3 h-3 rounded-full" style="background:{isLight ? '#fffbeb' : '#1c1400'};border:1px solid #f59e0b"></span>
				라우터 (외부 게이트웨이)
			</span>
			<span class="flex items-center gap-1.5">
				<span class="inline-block w-3 h-3 rounded-full" style="background:{isLight ? '#f8fafc' : '#0f172a'};border:1px solid #64748b"></span>
				라우터 (내부)
			</span>
			<span class="flex items-center gap-1.5">
				<span class="inline-block w-3 h-3 rounded" style="background:{isLight ? '#f0fdf4' : '#052e16'};border:1px solid #22c55e"></span>
				인스턴스 (ACTIVE)
			</span>
			<span class="flex items-center gap-1.5">
				<span class="inline-block w-3 h-3 rounded" style="background:{isLight ? '#fef2f2' : '#450a0a'};border:1px solid #ef4444"></span>
				인스턴스 (SHUTOFF/ERROR)
			</span>
			<span class="flex items-center gap-1.5">
				<span class="inline-block w-3 h-3 rounded" style="background:{isLight ? '#f8fafc' : '#1c1917'};border:1px solid #78716c"></span>
				인스턴스 (기타)
			</span>
		</div>

		<!-- 요약 (현재 프로젝트 기준) -->
		{@const _visibleNets = data.networks.filter(n => n.is_external || n.is_shared || n.project_id === $auth.projectId)}
		{@const _projectRouters = data.routers.filter(r => r.project_id === $auth.projectId)}
		{@const _projectFips = data.floating_ips.filter(f => !f.project_id || f.project_id === $auth.projectId)}
		<div class="mt-4 flex gap-6 text-xs text-gray-500 px-1">
			<span>네트워크 {_visibleNets.length}개</span>
			<span>라우터 {_projectRouters.length}개</span>
			<span>인스턴스 {data.instances.length}개</span>
			<span>Floating IP {_projectFips.length}개</span>
		</div>
	{/if}
</div>

{#if selectedInstanceId}
	<SlidePanel onClose={() => selectedInstanceId = null}>
		<InstanceDetailPanel instanceId={selectedInstanceId} onClose={() => selectedInstanceId = null} />
	</SlidePanel>
{/if}

{#if selectedRouterId}
	<SlidePanel onClose={() => selectedRouterId = null} width="w-full md:w-[60vw] max-w-3xl">
		<RouterDetailPanel routerId={selectedRouterId} onClose={() => selectedRouterId = null} />
	</SlidePanel>
{/if}
