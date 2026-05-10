<script lang="ts">
	import { api, ApiError } from '$lib/api/client';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';

	interface SubnetDetail {
		id: string;
		name: string;
		cidr: string;
		gateway_ip: string | null;
		dhcp_enabled: boolean;
	}

	interface RouterInfo {
		id: string;
		name: string;
		status: string;
		project_id: string | null;
		external_gateway_network_id: string | null;
		connected_subnet_ids: string[];
	}

	interface RouterListItem {
		id: string;
		name: string;
		status: string;
	}

	interface NetworkDetail {
		id: string;
		name: string;
		status: string;
		subnets: string[];
		is_external: boolean;
		is_shared: boolean;
		subnet_details: SubnetDetail[];
		routers: RouterInfo[];
	}

	interface Props {
		networkId: string;
		apiBase?: string;  // '/api/admin/networks' | '/api/networks'
		onClose?: () => void;
		token?: string;
		projectId?: string;
	}

	let { networkId, apiBase = '/api/admin/networks', onClose, token, projectId }: Props = $props();

	const isUserPanel = $derived(apiBase === '/api/networks');

	let network = $state<NetworkDetail | null>(null);
	let loading = $state(true);
	let error = $state('');

	// 라우터 연결 상태
	let allRouters = $state<RouterListItem[]>([]);
	let showRouterConnect = $state(false);
	let selectedRouterId = $state('');
	let selectedSubnetId = $state('');
	let connectingRouter = $state(false);

	const ar = createAutoRefresh(() => fetchNetwork(networkId), {
		storageKey: 'network-detail-panel',
		defaultActive: true,
		defaultInterval: 30,
		intervalOptions: [10, 15, 30, 60],
	});

	$effect(() => {
		if (!networkId) return;
		loading = true;
		error = '';
		network = null;
		showRouterConnect = false;
		fetchNetwork(networkId);
	});

	async function fetchNetwork(id: string) {
		try {
			network = await api.get<NetworkDetail>(`${apiBase}/${id}`, token, projectId);
		} catch (e) {
			error = e instanceof ApiError ? e.message : '네트워크 조회 실패';
		} finally {
			loading = false;
		}
	}

	async function openRouterConnect() {
		if (!allRouters.length) {
			try {
				allRouters = await api.get<RouterListItem[]>('/api/routers', token, projectId);
			} catch {
				allRouters = [];
			}
		}
		selectedRouterId = allRouters[0]?.id ?? '';
		selectedSubnetId = network?.subnet_details[0]?.id ?? '';
		showRouterConnect = true;
	}

	async function connectRouter() {
		if (!selectedRouterId || !selectedSubnetId) return;
		connectingRouter = true;
		try {
			const subnet = network?.subnet_details.find(s => s.id === selectedSubnetId);
			const autoGateway = !subnet?.gateway_ip;
			await api.post(
				`/api/routers/${selectedRouterId}/interfaces`,
				{ subnet_id: selectedSubnetId, auto_gateway: autoGateway },
				token,
				projectId
			);
			showRouterConnect = false;
			await fetchNetwork(networkId);
		} catch (e) {
			alert('라우터 연결 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			connectingRouter = false;
		}
	}

	async function disconnectRouter(router: RouterInfo) {
		const subnetIds = network?.subnet_details.map(s => s.id) ?? [];
		const targetSubnet = router.connected_subnet_ids.find(sid => subnetIds.includes(sid));
		if (!targetSubnet) {
			alert('연결된 서브넷을 찾을 수 없습니다.');
			return;
		}
		if (!confirm(`라우터 "${router.name || router.id.slice(0, 8)}"과의 연결을 해제하시겠습니까?`)) return;
		try {
			await api.delete(`/api/routers/${router.id}/interfaces/${targetSubnet}`, token, projectId);
			await fetchNetwork(networkId);
		} catch (e) {
			alert('라우터 연결 해제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		}
	}
</script>

<div class="flex flex-col h-full">
	<div class="flex items-center justify-between px-5 py-4 border-b border-gray-800 flex-shrink-0">
		<h2 class="text-sm font-semibold text-white truncate">{network?.name || networkId.slice(0, 12)}</h2>
		<div class="flex items-center gap-2 ml-3 flex-shrink-0">
			<AutoRefreshControl
				bind:active={ar.active}
				bind:intervalSeconds={ar.intervalSeconds}
				intervalOptions={ar.intervalOptions}
				refreshing={loading}
				onManualRefresh={() => fetchNetwork(networkId)}
			/>
			<button onclick={onClose} class="text-gray-400 hover:text-white text-xl leading-none">×</button>
		</div>
	</div>

	<div class="flex-1 overflow-y-auto p-5 space-y-4">
		{#if loading}
			<div class="text-gray-500 text-sm">로딩 중...</div>
		{:else if error}
			<div class="text-red-400 text-sm">{error}</div>
		{:else if network}
			<!-- 기본 정보 -->
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
				<h3 class="text-xs text-gray-500 uppercase tracking-wide mb-3">기본 정보</h3>
				<dl class="space-y-2 text-xs">
					<div class="flex justify-between">
						<dt class="text-gray-400">ID</dt>
						<dd class="text-gray-300 font-mono text-xs break-all">{network.id}</dd>
					</div>
					<div class="flex justify-between">
						<dt class="text-gray-400">상태</dt>
						<dd class="{network.status === 'ACTIVE' ? 'text-green-400' : 'text-gray-400'}">{network.status}</dd>
					</div>
					<div class="flex justify-between">
						<dt class="text-gray-400">유형</dt>
						<dd class="flex gap-1">
							{#if network.is_external}<span class="px-1.5 py-0.5 bg-orange-900/30 text-orange-300 rounded text-xs">외부</span>{/if}
							{#if network.is_shared}<span class="px-1.5 py-0.5 bg-blue-900/30 text-blue-300 rounded text-xs">공유</span>{/if}
							{#if !network.is_external && !network.is_shared}<span class="text-gray-500">내부</span>{/if}
						</dd>
					</div>
				</dl>
			</div>

			<!-- 서브넷 목록 -->
			{#if network.subnet_details.length > 0}
				<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
					<h3 class="text-xs text-gray-500 uppercase tracking-wide mb-3">서브넷 ({network.subnet_details.length})</h3>
					<div class="space-y-3">
						{#each network.subnet_details as subnet}
							<div class="border-b border-gray-800/50 pb-2 last:border-0 last:pb-0">
								<div class="text-xs text-white font-medium">{subnet.name || subnet.id.slice(0, 8)}</div>
								<dl class="mt-1 space-y-1 text-xs">
									<div class="flex justify-between">
										<dt class="text-gray-500">CIDR</dt>
										<dd class="text-gray-300 font-mono">{subnet.cidr}</dd>
									</div>
									<div class="flex justify-between">
										<dt class="text-gray-500">게이트웨이</dt>
										<dd class="text-gray-300 font-mono">{subnet.gateway_ip || '-'}</dd>
									</div>
									<div class="flex justify-between">
										<dt class="text-gray-500">DHCP</dt>
										<dd class="{subnet.dhcp_enabled ? 'text-green-400' : 'text-gray-500'}">{subnet.dhcp_enabled ? '활성' : '비활성'}</dd>
									</div>
								</dl>
							</div>
						{/each}
					</div>
				</div>
			{:else}
				<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
					<h3 class="text-xs text-gray-500 uppercase tracking-wide mb-2">서브넷</h3>
					<p class="text-xs text-gray-600">서브넷이 없습니다</p>
				</div>
			{/if}

			<!-- 연결된 라우터 -->
			{#if !network.is_external}
				<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
					<div class="flex items-center justify-between mb-3">
						<h3 class="text-xs text-gray-500 uppercase tracking-wide">연결된 라우터 ({network.routers.length})</h3>
						{#if isUserPanel}
							<button
								onclick={openRouterConnect}
								class="text-blue-400 hover:text-blue-300 text-xs px-2 py-1 rounded border border-blue-900 hover:border-blue-700 transition-colors"
							>+ 연결</button>
						{/if}
					</div>

					{#if showRouterConnect && isUserPanel}
						<div class="mb-3 p-3 bg-gray-800/60 border border-gray-700 rounded-lg space-y-2">
							<select bind:value={selectedRouterId} class="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-xs text-gray-200">
								<option value="">라우터 선택</option>
								{#each allRouters as r}
									<option value={r.id}>{r.name || r.id.slice(0, 12)}</option>
								{/each}
							</select>
							<select bind:value={selectedSubnetId} class="w-full bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-xs text-gray-200">
								<option value="">서브넷 선택</option>
								{#each network.subnet_details as subnet}
									<option value={subnet.id}>
										{subnet.name || subnet.cidr}{!subnet.gateway_ip ? ' (게이트웨이 자동 생성)' : ''}
									</option>
								{/each}
							</select>
							<div class="flex gap-2">
								<button
									onclick={connectRouter}
									disabled={!selectedRouterId || !selectedSubnetId || connectingRouter}
									class="bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 text-white text-xs px-3 py-1.5 rounded transition-colors"
								>{connectingRouter ? '연결 중...' : '연결'}</button>
								<button onclick={() => showRouterConnect = false} class="text-gray-400 hover:text-gray-200 text-xs px-2">취소</button>
							</div>
						</div>
					{/if}

					{#if network.routers.length > 0}
						<div class="space-y-2">
							{#each network.routers as router}
								<div class="flex items-center justify-between py-1">
									<div>
										<div class="text-xs text-white">{router.name || router.id.slice(0, 8)}</div>
										<div class="text-xs text-gray-500 font-mono">{router.id.slice(0, 12)}...</div>
									</div>
									<div class="flex items-center gap-2">
										<span class="text-xs {router.status === 'ACTIVE' ? 'text-green-400' : 'text-gray-400'}">{router.status}</span>
										{#if isUserPanel}
											<button
												onclick={() => disconnectRouter(router)}
												class="text-red-400 hover:text-red-300 text-xs px-1.5 py-0.5 rounded border border-red-900 hover:border-red-700 transition-colors"
											>해제</button>
										{/if}
									</div>
								</div>
							{/each}
						</div>
					{:else if !showRouterConnect}
						<p class="text-xs text-gray-600">연결된 라우터가 없습니다</p>
					{/if}
				</div>
			{/if}
		{/if}
	</div>
</div>
