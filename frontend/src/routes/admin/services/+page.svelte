<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import { siteConfig } from '$lib/config/site';

	interface Service {
		id: string;
		binary: string;
		host: string;
		status: string;
		state: string;
		zone: string;
		updated_at: string | null;
		disabled_reason: string | null;
	}
	interface NetworkAgent {
		id: string;
		binary: string;
		host: string;
		agent_type: string;
		availability_zone: string | null;
		alive: boolean | null;
		admin_state_up: boolean;
		updated_at: string | null;
	}
	interface EndpointGroup {
		service_id: string;
		name: string;
		service: string;
		region: string;
		endpoints: Record<string, string>;
	}
	interface StoragePool {
		name: string;
		volume_backend_name: string;
		driver_version: string;
		storage_protocol: string;
		vendor_name: string;
		total_capacity_gb: number;
		free_capacity_gb: number;
		allocated_capacity_gb: number;
	}

	type TabKey = 'compute' | 'network' | 'block_storage' | 'shared_file_system' | 'orchestration' | 'container' | 'container_infra' | 'endpoints' | 'storage_pools';

	let computeServices = $state<Service[]>([]);
	let blockStorageServices = $state<Service[]>([]);
	let networkAgents = $state<NetworkAgent[]>([]);
	let sharedFsServices = $state<Service[]>([]);
	let orchestrationServices = $state<Service[]>([]);
	let containerServices = $state<Service[]>([]);
	let magnumServices = $state<Service[]>([]);
	let endpoints = $state<EndpointGroup[]>([]);
	let storagePools = $state<StoragePool[]>([]);

	// 카테고리별 독립 로딩 상태
	const allCategories: TabKey[] = ['compute', 'network', 'block_storage', 'shared_file_system', 'orchestration', 'container', 'container_infra', 'endpoints', 'storage_pools'];

	// 선택적 서비스와 탭 키 매핑 (서비스가 비활성이면 탭 숨김)
	const serviceTabMap: Partial<Record<TabKey, keyof NonNullable<typeof $siteConfig>['services']>> = {
		container_infra: 'magnum',
		shared_file_system: 'manila',
		container: 'zun',
	};

	let visibleTabs = $derived(
		tabs.filter(tab => {
			const serviceKey = serviceTabMap[tab.key];
			if (!serviceKey) return true;
			return ($siteConfig?.services as Record<string, boolean>)?.[serviceKey] ?? false;
		})
	);

	let activeCategories = $derived(
		allCategories.filter(cat => {
			const serviceKey = serviceTabMap[cat];
			if (!serviceKey) return true;
			return ($siteConfig?.services as Record<string, boolean>)?.[serviceKey] ?? false;
		})
	);
	let loadingMap = $state<Record<TabKey, boolean>>(Object.fromEntries(allCategories.map(c => [c, true])) as Record<TabKey, boolean>);

	let autoRefresh = $state(true);
	let refreshInterval = $state(30);
	let lastRefresh = $state<Date | null>(null);
	let activeTab = $state<TabKey>('compute');

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	const tabs: { key: TabKey; label: string; count: () => number }[] = [
		{ key: 'compute', label: 'Compute', count: () => computeServices.length },
		{ key: 'network', label: 'Network', count: () => networkAgents.length },
		{ key: 'block_storage', label: 'Block Storage', count: () => blockStorageServices.length },
		{ key: 'shared_file_system', label: 'File Storage', count: () => sharedFsServices.length },
		{ key: 'orchestration', label: 'Orchestrator', count: () => orchestrationServices.length },
		{ key: 'container', label: 'Container', count: () => containerServices.length },
		{ key: 'container_infra', label: 'Magnum', count: () => magnumServices.length },
		{ key: 'endpoints', label: 'API Endpoints', count: () => endpoints.length },
		{ key: 'storage_pools', label: 'Storage Pools', count: () => storagePools.length },
	];

	async function loadCategory(cat: TabKey, isRefresh = false) {
		if (!isRefresh) loadingMap[cat] = true;
		try {
			const url = isRefresh ? `/api/admin/services?category=${cat}&refresh=true` : `/api/admin/services?category=${cat}`;
			const res = await api.get<Record<string, unknown>>(url, token, projectId);
			switch (cat) {
				case 'compute': computeServices = (res.compute as Service[]) || []; break;
				case 'block_storage': blockStorageServices = (res.block_storage as Service[]) || []; break;
				case 'network': networkAgents = (res.network as NetworkAgent[]) || []; break;
				case 'shared_file_system': sharedFsServices = (res.shared_file_system as Service[]) || []; break;
				case 'orchestration': orchestrationServices = (res.orchestration as Service[]) || []; break;
				case 'container': containerServices = (res.container as Service[]) || []; break;
				case 'container_infra': magnumServices = (res.container_infra as Service[]) || []; break;
				case 'endpoints': endpoints = (res.endpoints as EndpointGroup[]) || []; break;
				case 'storage_pools': storagePools = (res.storage_pools as StoragePool[]) || []; break;
			}
		} catch {
			// 조회 실패 시 빈 배열 유지
		} finally {
			loadingMap[cat] = false;
		}
	}

	function loadAll(isRefresh = false) {
		lastRefresh = new Date();
		activeCategories.forEach(cat => loadCategory(cat, isRefresh));
	}

	function refresh() {
		loadAll(true);
	}

	// activeTab이 숨겨진 탭이면 첫 번째 visible 탭으로 이동
	$effect(() => {
		if (visibleTabs.length > 0 && !visibleTabs.find(t => t.key === activeTab)) {
			activeTab = visibleTabs[0].key;
		}
	});

	onMount(() => { loadAll(); });

	$effect(() => {
		if (!autoRefresh) return;
		const interval = setInterval(() => loadAll(true), refreshInterval * 1000);
		return () => clearInterval(interval);
	});

	function fmtTime(s: string | null) {
		if (!s) return '-';
		return s.slice(0, 19).replace('T', ' ');
	}
</script>

<div class="p-4 md:p-8 max-w-7xl">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-white">서비스 상태</h1>
		<div class="flex items-center gap-3">
			{#if lastRefresh}
				<span class="text-xs text-gray-500">마지막: {lastRefresh.toLocaleTimeString()}</span>
			{/if}
			<button
				onclick={() => { autoRefresh = !autoRefresh; }}
				class="text-xs px-3 py-1.5 rounded border transition-colors {autoRefresh ? 'border-blue-500 bg-blue-900/20 text-blue-400' : 'border-gray-700 bg-gray-900 text-gray-400 hover:text-white'}"
			>{autoRefresh ? '자동 새로고침 ON' : '자동 새로고침 OFF'}</button>
			<button onclick={refresh} class="text-xs text-gray-400 hover:text-white transition-colors px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600">새로고침</button>
		</div>
	</div>

	<!-- 탭 바 -->
	<div class="flex flex-wrap gap-1 mb-6 border-b border-gray-800 pb-0">
		{#each visibleTabs as tab}
			<button
				onclick={() => activeTab = tab.key}
				class="px-3 py-2 text-xs font-medium rounded-t-lg transition-colors relative -mb-px border-b-2 {activeTab === tab.key
					? 'border-blue-500 text-blue-400 bg-blue-900/10'
					: 'border-transparent text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'}"
			>
				{tab.label}
				{#if loadingMap[tab.key]}
					<span class="ml-1.5 inline-block w-3 h-3 border border-gray-500 border-t-blue-400 rounded-full animate-spin"></span>
				{:else}
					<span class="ml-1.5 text-xs px-1.5 py-0.5 rounded-full {activeTab === tab.key ? 'bg-blue-900/50 text-blue-300' : 'bg-gray-800 text-gray-500'}">{tab.count()}</span>
				{/if}
			</button>
		{/each}
	</div>

	<!-- Compute (Nova) -->
	{#if activeTab === 'compute'}
		{#if loadingMap.compute}
			<LoadingSkeleton variant="table" rows={8} />
		{:else if computeServices.length === 0}
			<div class="text-gray-500 text-sm py-8 text-center">데이터 없음</div>
		{:else}
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
							<th class="text-left py-2 pr-4">Binary</th>
							<th class="text-left py-2 pr-4">Host</th>
							<th class="text-left py-2 pr-4">Zone</th>
							<th class="text-left py-2 pr-4">Status</th>
							<th class="text-left py-2 pr-4">State</th>
							<th class="text-left py-2 pr-4">Disabled Reason</th>
							<th class="text-left py-2">Updated</th>
						</tr>
					</thead>
					<tbody>
						{#each computeServices as s (s.id || s.binary + s.host)}
							<tr class="border-b border-gray-800/50 text-xs hover:bg-gray-800/30">
								<td class="py-2 pr-4 text-white font-mono">{s.binary}</td>
								<td class="py-2 pr-4 text-gray-300">{s.host}</td>
								<td class="py-2 pr-4 text-gray-400">{s.zone}</td>
								<td class="py-2 pr-4"><span class="px-1.5 py-0.5 rounded text-xs font-medium {s.status === 'enabled' ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}">{s.status}</span></td>
								<td class="py-2 pr-4"><span class="px-1.5 py-0.5 rounded text-xs font-medium {s.state === 'up' ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}">{s.state}</span></td>
								<td class="py-2 pr-4 text-gray-500">{s.disabled_reason || '-'}</td>
								<td class="py-2 text-gray-500">{fmtTime(s.updated_at)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	{/if}

	<!-- Network (Neutron) -->
	{#if activeTab === 'network'}
		{#if loadingMap.network}
			<LoadingSkeleton variant="table" rows={8} />
		{:else if networkAgents.length === 0}
			<div class="text-gray-500 text-sm py-8 text-center">데이터 없음</div>
		{:else}
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
							<th class="text-left py-2 pr-4">Agent Type</th>
							<th class="text-left py-2 pr-4">Binary</th>
							<th class="text-left py-2 pr-4">Host</th>
							<th class="text-left py-2 pr-4">Zone</th>
							<th class="text-left py-2 pr-4">Alive</th>
							<th class="text-left py-2 pr-4">Admin State</th>
							<th class="text-left py-2">Updated</th>
						</tr>
					</thead>
					<tbody>
						{#each networkAgents as a (a.id)}
							<tr class="border-b border-gray-800/50 text-xs hover:bg-gray-800/30">
								<td class="py-2 pr-4 text-white">{a.agent_type}</td>
								<td class="py-2 pr-4 text-gray-300 font-mono">{a.binary}</td>
								<td class="py-2 pr-4 text-gray-300">{a.host}</td>
								<td class="py-2 pr-4 text-gray-400">{a.availability_zone || '-'}</td>
								<td class="py-2 pr-4"><span class="px-1.5 py-0.5 rounded text-xs font-medium {a.alive ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}">{a.alive ? 'alive' : 'down'}</span></td>
								<td class="py-2 pr-4"><span class="px-1.5 py-0.5 rounded text-xs font-medium {a.admin_state_up ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}">{a.admin_state_up ? 'UP' : 'DOWN'}</span></td>
								<td class="py-2 text-gray-500">{fmtTime(a.updated_at)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	{/if}

	<!-- Block Storage (Cinder) -->
	{#if activeTab === 'block_storage'}
		{#if loadingMap.block_storage}
			<LoadingSkeleton variant="table" rows={8} />
		{:else if blockStorageServices.length === 0}
			<div class="text-gray-500 text-sm py-8 text-center">데이터 없음</div>
		{:else}
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
							<th class="text-left py-2 pr-4">Binary</th>
							<th class="text-left py-2 pr-4">Host</th>
							<th class="text-left py-2 pr-4">Zone</th>
							<th class="text-left py-2 pr-4">Status</th>
							<th class="text-left py-2 pr-4">State</th>
							<th class="text-left py-2 pr-4">Disabled Reason</th>
							<th class="text-left py-2">Updated</th>
						</tr>
					</thead>
					<tbody>
						{#each blockStorageServices as s (s.id || s.binary + s.host)}
							<tr class="border-b border-gray-800/50 text-xs hover:bg-gray-800/30">
								<td class="py-2 pr-4 text-white font-mono">{s.binary}</td>
								<td class="py-2 pr-4 text-gray-300">{s.host}</td>
								<td class="py-2 pr-4 text-gray-400">{s.zone}</td>
								<td class="py-2 pr-4"><span class="px-1.5 py-0.5 rounded text-xs font-medium {s.status === 'enabled' ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}">{s.status}</span></td>
								<td class="py-2 pr-4"><span class="px-1.5 py-0.5 rounded text-xs font-medium {s.state === 'up' ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}">{s.state}</span></td>
								<td class="py-2 pr-4 text-gray-500">{s.disabled_reason || '-'}</td>
								<td class="py-2 text-gray-500">{fmtTime(s.updated_at)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	{/if}

	<!-- File Storage (Manila) -->
	{#if activeTab === 'shared_file_system'}
		{#if loadingMap.shared_file_system}
			<LoadingSkeleton variant="table" rows={8} />
		{:else if sharedFsServices.length === 0}
			<div class="text-gray-500 text-sm py-8 text-center">Manila 서비스가 없거나 접근할 수 없습니다</div>
		{:else}
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
							<th class="text-left py-2 pr-4">Binary</th>
							<th class="text-left py-2 pr-4">Host</th>
							<th class="text-left py-2 pr-4">Zone</th>
							<th class="text-left py-2 pr-4">Status</th>
							<th class="text-left py-2 pr-4">State</th>
							<th class="text-left py-2">Updated</th>
						</tr>
					</thead>
					<tbody>
						{#each sharedFsServices as s (s.id || s.binary + s.host)}
							<tr class="border-b border-gray-800/50 text-xs hover:bg-gray-800/30">
								<td class="py-2 pr-4 text-white font-mono">{s.binary}</td>
								<td class="py-2 pr-4 text-gray-300">{s.host}</td>
								<td class="py-2 pr-4 text-gray-400">{s.zone}</td>
								<td class="py-2 pr-4"><span class="px-1.5 py-0.5 rounded text-xs font-medium {s.status === 'enabled' ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}">{s.status}</span></td>
								<td class="py-2 pr-4"><span class="px-1.5 py-0.5 rounded text-xs font-medium {s.state === 'up' ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}">{s.state}</span></td>
								<td class="py-2 text-gray-500">{fmtTime(s.updated_at)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	{/if}

	<!-- Orchestrator (Heat) -->
	{#if activeTab === 'orchestration'}
		{#if loadingMap.orchestration}
			<LoadingSkeleton variant="table" rows={8} />
		{:else if orchestrationServices.length === 0}
			<div class="text-gray-500 text-sm py-8 text-center">Heat 서비스가 없거나 접근할 수 없습니다</div>
		{:else}
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
							<th class="text-left py-2 pr-4">Binary</th>
							<th class="text-left py-2 pr-4">Host</th>
							<th class="text-left py-2 pr-4">Status</th>
							<th class="text-left py-2 pr-4">State</th>
							<th class="text-left py-2">Updated</th>
						</tr>
					</thead>
					<tbody>
						{#each orchestrationServices as s (s.id || s.binary + s.host)}
							<tr class="border-b border-gray-800/50 text-xs hover:bg-gray-800/30">
								<td class="py-2 pr-4 text-white font-mono">{s.binary}</td>
								<td class="py-2 pr-4 text-gray-300">{s.host}</td>
								<td class="py-2 pr-4"><span class="px-1.5 py-0.5 rounded text-xs font-medium {s.status === 'enabled' || s.status === 'up' ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}">{s.status}</span></td>
								<td class="py-2 pr-4"><span class="px-1.5 py-0.5 rounded text-xs font-medium {s.state === 'up' ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}">{s.state}</span></td>
								<td class="py-2 text-gray-500">{fmtTime(s.updated_at)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	{/if}

	<!-- Container (Zun) -->
	{#if activeTab === 'container'}
		{#if loadingMap.container}
			<LoadingSkeleton variant="table" rows={8} />
		{:else if containerServices.length === 0}
			<div class="text-gray-500 text-sm py-8 text-center">Zun 서비스가 없거나 접근할 수 없습니다</div>
		{:else}
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
							<th class="text-left py-2 pr-4">Binary</th>
							<th class="text-left py-2 pr-4">Host</th>
							<th class="text-left py-2 pr-4">Zone</th>
							<th class="text-left py-2 pr-4">Status</th>
							<th class="text-left py-2 pr-4">State</th>
							<th class="text-left py-2">Updated</th>
						</tr>
					</thead>
					<tbody>
						{#each containerServices as s (s.id || s.binary + s.host)}
							<tr class="border-b border-gray-800/50 text-xs hover:bg-gray-800/30">
								<td class="py-2 pr-4 text-white font-mono">{s.binary}</td>
								<td class="py-2 pr-4 text-gray-300">{s.host}</td>
								<td class="py-2 pr-4 text-gray-400">{s.zone}</td>
								<td class="py-2 pr-4"><span class="px-1.5 py-0.5 rounded text-xs font-medium {s.status === 'enabled' || s.status === 'up' ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}">{s.status}</span></td>
								<td class="py-2 pr-4"><span class="px-1.5 py-0.5 rounded text-xs font-medium {s.state === 'up' ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}">{s.state}</span></td>
								<td class="py-2 text-gray-500">{fmtTime(s.updated_at)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	{/if}

	<!-- Magnum (Container Infra) -->
	{#if activeTab === 'container_infra'}
		{#if loadingMap.container_infra}
			<LoadingSkeleton variant="table" rows={8} />
		{:else if magnumServices.length === 0}
			<div class="text-gray-500 text-sm py-8 text-center">Magnum 서비스가 없거나 접근할 수 없습니다</div>
		{:else}
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
							<th class="text-left py-2 pr-4">Binary</th>
							<th class="text-left py-2 pr-4">Host</th>
							<th class="text-left py-2 pr-4">Status</th>
							<th class="text-left py-2 pr-4">State</th>
							<th class="text-left py-2 pr-4">Disabled Reason</th>
							<th class="text-left py-2">Updated</th>
						</tr>
					</thead>
					<tbody>
						{#each magnumServices as s (s.id || s.binary + s.host)}
							<tr class="border-b border-gray-800/50 text-xs hover:bg-gray-800/30">
								<td class="py-2 pr-4 text-white font-mono">{s.binary}</td>
								<td class="py-2 pr-4 text-gray-300">{s.host}</td>
								<td class="py-2 pr-4"><span class="px-1.5 py-0.5 rounded text-xs font-medium {s.status === 'enabled' || s.status === 'up' ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}">{s.status}</span></td>
								<td class="py-2 pr-4"><span class="px-1.5 py-0.5 rounded text-xs font-medium {s.state === 'up' ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}">{s.state}</span></td>
								<td class="py-2 pr-4 text-gray-500">{s.disabled_reason || '-'}</td>
								<td class="py-2 text-gray-500">{fmtTime(s.updated_at)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	{/if}

	<!-- API Endpoints -->
	{#if activeTab === 'endpoints'}
		{#if loadingMap.endpoints}
			<LoadingSkeleton variant="table" rows={8} />
		{:else if endpoints.length === 0}
			<div class="text-gray-500 text-sm py-8 text-center">엔드포인트 정보를 가져올 수 없습니다</div>
		{:else}
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
							<th class="text-left py-2 pr-6">Name</th>
							<th class="text-left py-2 pr-6">Service</th>
							<th class="text-left py-2 pr-6">Region</th>
							<th class="text-left py-2">Endpoints</th>
						</tr>
					</thead>
					<tbody>
						{#each [...endpoints].sort((a, b) => (a.name || '').localeCompare(b.name || '')) as ep (ep.service_id)}
							<tr class="border-b border-gray-800/50 text-xs hover:bg-gray-800/30 align-top">
								<td class="py-3 pr-6 text-white font-medium">{ep.name}</td>
								<td class="py-3 pr-6 text-gray-400">{ep.service}</td>
								<td class="py-3 pr-6 text-gray-400">{ep.region}</td>
								<td class="py-3">
									<div class="space-y-1">
										{#each Object.entries(ep.endpoints).sort() as [iface, url]}
											<div class="flex items-start gap-2">
												<span class="text-gray-500 w-14 shrink-0 font-medium">{iface}:</span>
												<span class="text-gray-300 font-mono break-all">{url}</span>
											</div>
										{/each}
									</div>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	{/if}

	<!-- Storage Pools -->
	{#if activeTab === 'storage_pools'}
		{#if loadingMap.storage_pools}
			<LoadingSkeleton variant="table" rows={4} />
		{:else if storagePools.length === 0}
			<div class="text-gray-500 text-sm py-8 text-center">스토리지 풀 정보를 가져올 수 없습니다</div>
		{:else}
			<div class="space-y-4">
				{#each storagePools as pool (pool.name)}
					{@const usedGb = pool.total_capacity_gb - pool.free_capacity_gb}
					{@const pct = pool.total_capacity_gb > 0 ? Math.min(100, (usedGb / pool.total_capacity_gb) * 100) : 0}
					<div class="bg-gray-900 border border-gray-800 rounded-xl p-5">
						<div class="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-4">
							<div>
								<div class="text-sm font-medium text-white">{pool.name}</div>
								<div class="text-xs text-gray-500 mt-0.5">
									{#if pool.storage_protocol}<span class="mr-3">Protocol: {pool.storage_protocol}</span>{/if}
									{#if pool.volume_backend_name}<span class="mr-3">Backend: {pool.volume_backend_name}</span>{/if}
									{#if pool.vendor_name}<span>Vendor: {pool.vendor_name}</span>{/if}
								</div>
							</div>
							<div class="text-right">
								<div class="text-sm text-white">
									<span class="font-medium">{usedGb.toFixed(1)}</span>
									<span class="text-gray-400"> / {pool.total_capacity_gb.toFixed(1)} GiB</span>
								</div>
								<div class="text-xs text-gray-500">여유: {pool.free_capacity_gb.toFixed(1)} GiB</div>
							</div>
						</div>
						<div class="w-full h-2 bg-gray-800 rounded-full overflow-hidden">
							<div
								class="h-full rounded-full transition-all {pct > 85 ? 'bg-red-500' : pct > 65 ? 'bg-yellow-500' : 'bg-blue-500'}"
								style="width: {pct.toFixed(1)}%"
							></div>
						</div>
						<div class="text-xs text-gray-500 mt-1">{pct.toFixed(1)}% 사용 중</div>
					</div>
				{/each}
			</div>
		{/if}
	{/if}

</div>
