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

	interface TrafficRate { rx_bps: number; tx_bps: number; }
	interface TopologyTraffic {
		ts: number;
		instances: Record<string, TrafficRate>;
		networks: Record<string, TrafficRate>;
		routers: Record<string, TrafficRate>;
		load_balancers: Record<string, TrafficRate>;
		_meta?: { router_traffic?: string };
	}

	let data = $state<TopologyData | null>(null);
	let loading = $state(true);
	let refreshing = $state(false);
	let error = $state('');
	let traffic = $state<TopologyTraffic | null>(null);
	let selectedInstanceId = $state<string | null>(null);
	let selectedRouterId = $state<string | null>(null);
	let selectedLB = $state<TopologyLoadBalancer | null>(null);

	// 토폴로지 선택 상태를 부모에서 파생 (패널 닫을 때 자동 highlight 해제)
	const topologySelectedId = $derived(
		selectedInstanceId ?? selectedRouterId ?? selectedLB?.id ?? null
	);

	const ar = createAutoRefresh(() => fetchTopology(), {
		storageKey: 'dashboard-network-topology',
		defaultActive: true,
		defaultInterval: 30,
		intervalOptions: [10, 15, 30, 60],
	});

	async function loadTraffic() {
		if (!$auth.token) return;
		try {
			traffic = await api.get<TopologyTraffic>(
				'/api/networks/topology/traffic',
				$auth.token ?? undefined,
				$auth.projectId ?? undefined,
			);
		} catch { /* silent — 토폴로지 표시는 traffic=null 로 유지 */ }
	}

	const arTraffic = createAutoRefresh(loadTraffic, {
		storageKey: 'dashboard-network-topology-traffic',
		defaultActive: true,
		defaultInterval: 15,
		intervalOptions: [10, 15, 30],
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
				{traffic}
				projectId={$auth.projectId}
				selectedId={topologySelectedId}
				onSelectInstance={(id) => {
					if (selectedInstanceId === id) { selectedInstanceId = null; }
					else { selectedInstanceId = id; selectedRouterId = null; selectedLB = null; }
				}}
				onSelectRouter={(id) => {
					if (selectedRouterId === id) { selectedRouterId = null; }
					else { selectedRouterId = id; selectedInstanceId = null; selectedLB = null; }
				}}
				onSelectLoadBalancer={(lb) => {
					if (selectedLB?.id === lb.id) { selectedLB = null; }
					else { selectedLB = lb; selectedInstanceId = null; selectedRouterId = null; }
				}}
			/>
		</div>

		<!-- 범례 -->
		<div class="flex flex-wrap gap-x-5 gap-y-2 text-xs px-1"
		     style="color: {isLight ? '#4b5563' : '#9ca3af'}">
			<!-- 상태 dot -->
			<span class="flex items-center gap-1.5">
				<span class="w-2 h-2 rounded-full bg-green-400 flex-shrink-0"></span>ACTIVE
			</span>
			<span class="flex items-center gap-1.5">
				<span class="w-2 h-2 rounded-full bg-red-400 flex-shrink-0"></span>ERROR / SHUTOFF
			</span>
			<span class="flex items-center gap-1.5">
				<span class="w-2 h-2 rounded-full bg-yellow-400 animate-pulse flex-shrink-0"></span>PENDING / 기타
			</span>
			<!-- 자원 타입 아이콘 -->
			<span class="flex items-center gap-1.5">
				<svg class="w-3.5 h-3.5 flex-shrink-0 text-amber-400" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
					<circle cx="8" cy="8" r="6"/><circle cx="8" cy="8" r="2" fill="currentColor" opacity="0.5"/>
					<path d="M8 2v2M8 12v2M2 8h2M12 8h2"/>
				</svg>
				라우터
			</span>
			<span class="flex items-center gap-1.5">
				<svg class="w-3.5 h-3.5 flex-shrink-0 text-cyan-400" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5">
					<line x1="8" y1="2" x2="8" y2="14"/><line x1="3" y1="5" x2="13" y2="5"/><line x1="4" y1="11" x2="12" y2="11" opacity="0.6"/>
				</svg>
				로드밸런서
			</span>
			<span class="flex items-center gap-1.5">
				<svg class="w-3.5 h-3.5 flex-shrink-0 text-gray-400" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.3">
					<ellipse cx="8" cy="5" rx="5" ry="2"/><line x1="3" y1="5" x2="3" y2="11"/><line x1="13" y1="5" x2="13" y2="11"/>
					<path d="M3 11 a5 2 0 0 0 10 0"/>
				</svg>
				인스턴스
			</span>
			<!-- 네트워크 종류 (세로 바) -->
			<span class="flex items-center gap-1.5">
				<span class="w-0.5 h-4 flex-shrink-0 rounded-full" style="background:#ea580c"></span>외부 네트워크
			</span>
			<span class="flex items-center gap-1.5">
				<span class="w-0.5 h-4 flex-shrink-0 rounded-full" style="background:#0d9488"></span>공유 네트워크
			</span>
			<span class="flex items-center gap-1.5">
				<span class="w-0.5 h-4 flex-shrink-0 rounded-full" style="background:#3b82f6"></span>내부 네트워크
			</span>
			<!-- 마커 -->
			<span class="flex items-center gap-1.5">
				<span class="text-[10px] text-orange-400 font-mono flex-shrink-0">✦</span>Floating IP
			</span>
			<span class="flex items-center gap-1.5">
				<span class="text-[9px] px-1 rounded bg-blue-900/40 text-blue-400 flex-shrink-0">2NIC</span>멀티 NIC
			</span>
			<!-- 연결선 -->
			<span class="flex items-center gap-1.5">
				<span class="inline-block w-6 h-0.5 flex-shrink-0 rounded-full" style="background:#3b82f6"></span>연결 (굵기=트래픽)
			</span>
			<span class="flex items-center gap-1.5">
				<span class="inline-block w-6 h-0.5 flex-shrink-0" style="background-image:repeating-linear-gradient(90deg,#f59e0b 0,#f59e0b 4px,transparent 4px,transparent 7px)"></span>LB → 멤버
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
