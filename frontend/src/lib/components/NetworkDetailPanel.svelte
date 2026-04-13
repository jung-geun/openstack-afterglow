<script lang="ts">
	import { api, ApiError } from '$lib/api/client';

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

	let network = $state<NetworkDetail | null>(null);
	let loading = $state(true);
	let error = $state('');

	$effect(() => {
		if (!networkId) return;
		loading = true;
		error = '';
		network = null;
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
</script>

<div class="flex flex-col h-full">
	<div class="flex items-center justify-between px-5 py-4 border-b border-gray-800 flex-shrink-0">
		<h2 class="text-sm font-semibold text-white truncate">{network?.name || networkId.slice(0, 12)}</h2>
		<button onclick={onClose} class="text-gray-400 hover:text-white text-xl leading-none ml-3 flex-shrink-0">×</button>
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
			{#if network.routers.length > 0}
				<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
					<h3 class="text-xs text-gray-500 uppercase tracking-wide mb-3">연결된 라우터 ({network.routers.length})</h3>
					<div class="space-y-2">
						{#each network.routers as router}
							<div class="flex items-center justify-between py-1">
								<div>
									<div class="text-xs text-white">{router.name || router.id.slice(0, 8)}</div>
									<div class="text-xs text-gray-500 font-mono">{router.id.slice(0, 12)}...</div>
								</div>
								<span class="text-xs {router.status === 'ACTIVE' ? 'text-green-400' : 'text-gray-400'}">{router.status}</span>
							</div>
						{/each}
					</div>
				</div>
			{/if}
		{/if}
	</div>
</div>
