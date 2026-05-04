<script lang="ts">
	import { untrack } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import GlobalTopology from '$lib/components/GlobalTopology.svelte';
	import InstanceDetailPanel from '$lib/components/InstanceDetailPanel.svelte';
	import RouterDetailPanel from '$lib/components/RouterDetailPanel.svelte';
	import SlidePanel from '$lib/components/SlidePanel.svelte';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';

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
		external_gateway_ips: string[];
		interface_ips: { ip_address: string; subnet_id: string }[];
		is_distributed: boolean;
		is_ha: boolean;
		connected_subnet_ids: string[];
		dvr_subnet_ids: string[];
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
	interface TopologyLBMember {
		id: string; address: string; protocol_port: number;
		status: string; subnet_id: string | null; pool_id: string; server_id: string | null;
	}
	interface TopologyLBListener {
		id: string; name: string; protocol: string; protocol_port: number;
		default_pool_id: string | null;
	}
	interface TopologyLoadBalancer {
		id: string; name: string;
		vip_address: string | null; vip_port_id: string | null;
		vip_subnet_id: string | null; vip_network_id: string | null;
		provisioning_status: string; operating_status: string;
		project_id: string | null;
		listeners: TopologyLBListener[];
		members: TopologyLBMember[];
	}
	interface TopologyData {
		networks: TopologyNetwork[];
		routers: TopologyRouter[];
		instances: TopologyInstance[];
		floating_ips: FloatingIpInfo[];
		load_balancers?: TopologyLoadBalancer[];
	}

	let data = $state<TopologyData | null>(null);
	let loading = $state(true);
	let refreshing = $state(false);
	let error = $state('');
	let selectedInstanceId = $state<string | null>(null);
	let selectedRouterId = $state<string | null>(null);
	let selectedLB = $state<TopologyLoadBalancer | null>(null);

	const ar = createAutoRefresh(() => fetchTopology(), {
		storageKey: 'dashboard-network-topology',
		defaultActive: true,
		defaultInterval: 30,
		intervalOptions: [10, 15, 30, 60],
	});

	$effect(() => {
		if (!$auth.token || !$auth.projectId) return;
		untrack(() => fetchTopology());
	});

	async function fetchTopology(opts?: { refresh?: boolean }) {
		if (!data) loading = true;
		else refreshing = true;
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
			refreshing = false;
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
	<PageHeader breadcrumb="NETWORK / TOPOLOGY" title="토폴로지">
		{#snippet actions()}
			<AutoRefreshControl
			bind:active={ar.active}
			bind:intervalSeconds={ar.intervalSeconds}
			intervalOptions={ar.intervalOptions}
			refreshing={refreshing || loading}
			onManualRefresh={forceRefresh}
		/>
		{/snippet}
	</PageHeader>

	{#if error}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">
			{error}
		</div>
	{:else if loading}
		<LoadingSkeleton variant="card" rows={8} />
	{:else if data}
		{@const _visibleNets = data.networks.filter(n => n.is_external || n.is_shared || n.project_id === $auth.projectId)}
		{@const _projectRouters = data.routers.filter(r => r.project_id === $auth.projectId)}
		{@const _projectFips = data.floating_ips.filter(f => !f.project_id || f.project_id === $auth.projectId)}
		<div class:opacity-60={refreshing} class:pointer-events-none={refreshing}>
		<div class="bg-gray-900 border border-gray-800 rounded-lg p-6 mb-4">
			<GlobalTopology
				{data}
				projectId={$auth.projectId}
				onSelectInstance={(id) => { selectedInstanceId = id; }}
				onSelectRouter={(id) => { selectedRouterId = id; }}
				onSelectLoadBalancer={(lb) => { selectedLB = lb; }}
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
			<span class="flex items-center gap-1.5">
				<span class="inline-block w-3 h-3 rounded" style="background:{isLight ? '#ecfeff' : '#083344'};border:1px solid #06b6d4"></span>
				로드밸런서
			</span>
		</div>

		<!-- 요약 (현재 프로젝트 기준) -->
		<div class="mt-4 flex gap-6 text-xs text-gray-500 px-1">
			<span>네트워크 {_visibleNets.length}개</span>
			<span>라우터 {_projectRouters.length}개</span>
			<span>인스턴스 {data.instances.length}개</span>
			<span>Floating IP {_projectFips.length}개</span>
			<span>로드밸런서 {(data.load_balancers ?? []).filter(lb => !lb.project_id || lb.project_id === $auth.projectId).length}개</span>
		</div>
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

{#if selectedLB}
	<SlidePanel onClose={() => selectedLB = null} width="w-full md:w-[60vw] max-w-2xl">
		<div class="p-6 space-y-5">
			<div class="flex items-start justify-between">
				<div>
					<h2 class="text-lg font-semibold text-white">{selectedLB.name || '로드밸런서'}</h2>
					<p class="text-xs text-gray-400 mt-0.5 font-mono">{selectedLB.id}</p>
				</div>
				<button onclick={() => selectedLB = null} class="text-gray-400 hover:text-white text-xl leading-none">×</button>
			</div>
			<div class="grid grid-cols-2 gap-3 text-sm">
				<div class="bg-gray-800 rounded-lg p-3">
					<p class="text-gray-400 text-xs mb-1">VIP 주소</p>
					<p class="text-white font-mono">{selectedLB.vip_address ?? '-'}</p>
				</div>
				<div class="bg-gray-800 rounded-lg p-3">
					<p class="text-gray-400 text-xs mb-1">프로비저닝 상태</p>
					<p class="font-medium" style="color:{selectedLB.provisioning_status === 'ACTIVE' ? '#22c55e' : '#f59e0b'}">{selectedLB.provisioning_status}</p>
				</div>
				<div class="bg-gray-800 rounded-lg p-3">
					<p class="text-gray-400 text-xs mb-1">운영 상태</p>
					<p class="font-medium" style="color:{selectedLB.operating_status === 'ONLINE' ? '#22c55e' : '#94a3b8'}">{selectedLB.operating_status}</p>
				</div>
			</div>
			{#if selectedLB.listeners.length > 0}
				<div>
					<h3 class="text-sm font-medium text-gray-300 mb-2">리스너</h3>
					<div class="space-y-1.5">
						{#each selectedLB.listeners as li}
							<div class="bg-gray-800 rounded-lg px-3 py-2 text-sm flex items-center gap-3">
								<span class="text-cyan-400 font-mono text-xs">{li.protocol}:{li.protocol_port}</span>
								<span class="text-gray-300 truncate">{li.name || li.id}</span>
							</div>
						{/each}
					</div>
				</div>
			{/if}
			{#if selectedLB.members.length > 0}
				<div>
					<h3 class="text-sm font-medium text-gray-300 mb-2">멤버 ({selectedLB.members.length}개)</h3>
					<div class="space-y-1.5">
						{#each selectedLB.members as m}
							<div class="bg-gray-800 rounded-lg px-3 py-2 text-sm flex items-center gap-3">
								<span class="w-2 h-2 rounded-full flex-shrink-0" style="background:{m.status === 'ACTIVE' ? '#22c55e' : m.status === 'ERROR' ? '#ef4444' : '#64748b'}"></span>
								<span class="text-white font-mono text-xs">{m.address}:{m.protocol_port}</span>
								<span class="text-gray-500 text-xs">{m.status}</span>
								{#if !m.server_id}
									<span class="text-xs text-yellow-600">외부 호스트</span>
								{/if}
							</div>
						{/each}
					</div>
				</div>
			{/if}
		</div>
	</SlidePanel>
{/if}
