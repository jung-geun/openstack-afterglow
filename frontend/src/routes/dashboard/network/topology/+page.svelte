<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import GlobalTopology from '$lib/components/GlobalTopology.svelte';
	import InstanceDetailPanel from '$lib/components/InstanceDetailPanel.svelte';
	import RouterDetailPanel from '$lib/components/RouterDetailPanel.svelte';

	let isLight = $state(false);
	onMount(() => {
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
	let error = $state('');
	let selectedInstanceId = $state<string | null>(null);
	let selectedRouterId = $state<string | null>(null);

	$effect(() => {
		if (!$auth.token) return;
		fetchTopology();
	});

	async function fetchTopology() {
		loading = true;
		error = '';
		try {
			data = await api.get<TopologyData>(
				'/api/networks/topology',
				$auth.token ?? undefined,
				$auth.projectId ?? undefined
			);
		} catch (e) {
			error = e instanceof ApiError ? `조회 실패 (${e.status}): ${e.message}` : '서버 오류';
		} finally {
			loading = false;
		}
	}
</script>

<div class="p-8 max-w-screen-2xl mx-auto">
	<div class="mb-6 flex items-center justify-between">
		<h1 class="text-2xl font-bold text-white">네트워크 토폴로지</h1>
		<button
			onclick={fetchTopology}
			disabled={loading}
			class="text-sm px-3 py-1.5 rounded border border-gray-700 text-gray-400 hover:text-gray-200 hover:border-gray-500 disabled:text-gray-600 disabled:border-gray-800 transition-colors"
		>
			{loading ? '로딩 중…' : '새로고침'}
		</button>
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
	<div
		class="fixed inset-0 z-40"
		role="dialog"
		aria-modal="true"
		onkeydown={(e) => e.key === 'Escape' && (selectedInstanceId = null)}
		tabindex="-1"
	>
		<div class="absolute inset-0 bg-black/50" onclick={() => selectedInstanceId = null}></div>
		<div class="absolute right-0 top-14 bottom-0 w-[75vw] max-w-5xl bg-gray-950 border-l border-gray-700 overflow-y-auto shadow-2xl">
			<InstanceDetailPanel instanceId={selectedInstanceId} onClose={() => selectedInstanceId = null} />
		</div>
	</div>
{/if}

{#if selectedRouterId}
	<div
		class="fixed inset-0 z-40"
		role="dialog"
		aria-modal="true"
		onkeydown={(e) => e.key === 'Escape' && (selectedRouterId = null)}
		tabindex="-1"
	>
		<div class="absolute inset-0 bg-black/50" onclick={() => selectedRouterId = null}></div>
		<div class="absolute right-0 top-14 bottom-0 w-[60vw] max-w-3xl bg-gray-950 border-l border-gray-700 overflow-y-auto shadow-2xl">
			<RouterDetailPanel routerId={selectedRouterId} onClose={() => selectedRouterId = null} />
		</div>
	</div>
{/if}
