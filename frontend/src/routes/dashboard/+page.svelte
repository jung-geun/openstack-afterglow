<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { api, ApiError, memoryCache } from '$lib/api/client';
	import { goto } from '$app/navigation';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';

	interface IpAddress {
		addr: string;
		type: string;
		network_name: string;
	}

	interface Instance {
		id: string;
		name: string;
		status: string;
		image_name: string | null;
		flavor_name: string | null;
		ip_addresses: IpAddress[];
		created_at: string | null;
		union_libraries: string[];
		union_strategy: string | null;
	}

	interface Volume {
		id: string;
		name: string;
		status: string;
		size: number;
		volume_type: string | null;
		attachments: Record<string, unknown>[];
	}

	interface Share {
		id: string;
		name: string;
		status: string;
		size: number;
		share_proto: string;
		export_locations: string[];
		metadata: Record<string, string>;
		library_name: string | null;
		library_version: string | null;
		built_at: string | null;
	}

	interface Network {
		id: string;
		name: string;
		status: string;
		subnets: string[];
		is_external: boolean;
		is_shared: boolean;
	}

	interface DashboardSummary {
		instances: { total: number; active: number; shutoff: number; error: number };
		compute: { instances_used: number; instances_limit: number; vcpus_used: number; vcpus_limit: number; ram_used_mb: number; ram_limit_mb: number };
		storage: { volumes_used: number; volumes_limit: number; gigabytes_used: number; gigabytes_limit: number };
		gpu_used: number;
	}

	interface Router {
		id: string;
		name: string;
		status: string;
		external_gateway_network_id: string | null;
		connected_subnet_ids: string[];
	}

	type Tab = 'instances' | 'volumes' | 'shares' | 'networks' | 'routers' | 'loadbalancers';

	interface LoadBalancer {
		id: string;
		name: string;
		status: string;
		operating_status: string;
		vip_address: string | null;
		vip_subnet_id: string | null;
	}

	let instances = $state<Instance[]>([]);
	let volumes = $state<Volume[]>([]);
	let shares = $state<Share[]>([]);
	let networks = $state<Network[]>([]);
	let routers = $state<Router[]>([]);
	let loadBalancers = $state<LoadBalancer[]>([]);
	let summary = $state<DashboardSummary | null>(null);
	let loading = $state(true);
	let instancesError = $state('');
	let volumesError = $state('');
	let sharesError = $state('');
	let networksError = $state('');
	let routersError = $state('');
	let lbError = $state('');
	let deleting = $state<string | null>(null);
	let activeTab = $state<Tab>('instances');

	// 생성 모달 상태
	let showVolumeModal = $state(false);
	let showShareModal = $state(false);
	let showNetworkModal = $state(false);
	let showRouterModal = $state(false);

	let volForm = $state({ name: '', size_gb: 10 });
	let shareForm = $state({ name: '', size_gb: 50 });
	let netForm = $state({
		name: '',
		addSubnet: false,
		subnetName: '',
		cidr: '10.0.0.0/24',
		gateway: '',
		dhcp: true,
	});
	let routerForm = $state({ name: '', external_network_id: '' });

	let creating = $state(false);
	let createError = $state('');

	let instanceNameMap = $derived(new Map(instances.map((i) => [i.id, i.name])));

	const tabLabels: Record<Tab, string> = {
		instances: '인스턴스',
		volumes: '볼륨',
		shares: '공유(Share)',
		networks: '네트워크',
		routers: '라우터',
		loadbalancers: '로드밸런서',
	};

	function tabCount(tab: Tab): number {
		if (tab === 'instances') return instances.length;
		if (tab === 'volumes') return volumes.length;
		if (tab === 'shares') return shares.length;
		if (tab === 'routers') return routers.length;
		if (tab === 'loadbalancers') return loadBalancers.length;
		return networks.length;
	}

	function swrGet<T>(path: string): T | null {
		const key = `${path}:${$auth.projectId}`;
		const c = memoryCache.get(key);
		return c ? (c.data as T) : null;
	}

	function swrSet(path: string, data: unknown) {
		memoryCache.set(`${path}:${$auth.projectId}`, { data, timestamp: Date.now() });
	}

	async function fetchInstances() {
		const path = '/api/instances';
		const cached = swrGet<Instance[]>(path);
		if (cached && instances.length === 0) instances = cached;
		try {
			instances = await api.get<Instance[]>(path, $auth.token ?? undefined, $auth.projectId ?? undefined);
			swrSet(path, instances);
			instancesError = '';
		} catch (e) {
			if (!cached) instancesError = e instanceof ApiError ? `조회 실패 (${e.status}): ${(e as ApiError).message}` : '서버 오류';
		}
	}

	async function fetchVolumes() {
		const path = '/api/volumes';
		const cached = swrGet<Volume[]>(path);
		if (cached && volumes.length === 0) volumes = cached;
		try {
			volumes = await api.get<Volume[]>(path, $auth.token ?? undefined, $auth.projectId ?? undefined);
			swrSet(path, volumes);
			volumesError = '';
		} catch (e) {
			if (!cached) volumesError = e instanceof ApiError ? `조회 실패 (${e.status}): ${(e as ApiError).message}` : '서버 오류';
		}
	}

	async function fetchShares() {
		const path = '/api/shares';
		const cached = swrGet<Share[]>(path);
		if (cached && shares.length === 0) shares = cached;
		try {
			shares = await api.get<Share[]>(path, $auth.token ?? undefined, $auth.projectId ?? undefined);
			swrSet(path, shares);
			sharesError = '';
		} catch (e) {
			if (!cached) sharesError = e instanceof ApiError ? `조회 실패 (${e.status}): ${(e as ApiError).message}` : '서버 오류';
		}
	}

	async function fetchNetworks() {
		const path = '/api/networks';
		const cached = swrGet<Network[]>(path);
		if (cached && networks.length === 0) networks = cached;
		try {
			networks = await api.get<Network[]>(path, $auth.token ?? undefined, $auth.projectId ?? undefined);
			swrSet(path, networks);
			networksError = '';
		} catch (e) {
			if (!cached) networksError = e instanceof ApiError ? `조회 실패 (${e.status}): ${(e as ApiError).message}` : '서버 오류';
		}
	}

	async function fetchRouters() {
		const path = '/api/routers';
		const cached = swrGet<Router[]>(path);
		if (cached && routers.length === 0) routers = cached;
		try {
			routers = await api.get<Router[]>(path, $auth.token ?? undefined, $auth.projectId ?? undefined);
			swrSet(path, routers);
			routersError = '';
		} catch (e) {
			if (!cached) routersError = e instanceof ApiError ? `조회 실패 (${e.status}): ${(e as ApiError).message}` : '서버 오류';
		}
	}

	async function fetchLoadBalancers() {
		const path = '/api/loadbalancers';
		const cached = swrGet<LoadBalancer[]>(path);
		if (cached && loadBalancers.length === 0) loadBalancers = cached;
		try {
			loadBalancers = await api.get<LoadBalancer[]>(path, $auth.token ?? undefined, $auth.projectId ?? undefined);
			swrSet(path, loadBalancers);
			lbError = '';
		} catch {
			// Octavia가 없는 환경에서는 조용히 실패
			lbError = '';
		}
	}

	async function fetchSummary() {
		const path = '/api/dashboard/summary';
		const cached = swrGet<DashboardSummary>(path);
		if (cached && !summary) summary = cached;
		try {
			summary = await api.get<DashboardSummary>(path, $auth.token ?? undefined, $auth.projectId ?? undefined);
			swrSet(path, summary);
		} catch {
			// summary는 실패해도 나머지 UI에 영향 없음
		}
	}

	let refreshIntervalMs = $state(5000);

	async function loadConfig() {
		try {
			const cfg = await api.get<{ refresh_interval_ms: number }>('/api/dashboard/config', $auth.token ?? undefined, $auth.projectId ?? undefined);
			refreshIntervalMs = cfg.refresh_interval_ms;
		} catch {
			// 기본값 유지
		}
	}

	async function fetchAllData() {
		await Promise.allSettled([
			fetchInstances(),
			fetchVolumes(),
			fetchShares(),
			fetchNetworks(),
			fetchRouters(),
			fetchLoadBalancers(),
			fetchSummary(),
		]);
		loading = false;
	}

	async function deleteInstance(id: string, name: string) {
		if (!confirm(`"${name}" 인스턴스를 삭제하시겠습니까?\nManila share와 볼륨도 함께 삭제됩니다.`)) return;
		deleting = id;
		try {
			await api.delete(`/api/instances/${id}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
			await fetchAllData();
		} catch (e) {
			alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
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

	async function createVolume() {
		if (!volForm.name.trim() || volForm.size_gb < 1) return;
		creating = true;
		createError = '';
		try {
			await api.post('/api/volumes', volForm, $auth.token ?? undefined, $auth.projectId ?? undefined);
			showVolumeModal = false;
			volForm = { name: '', size_gb: 10 };
			await fetchVolumes();
		} catch (e) {
			createError = e instanceof ApiError ? e.message : '생성 실패';
		} finally {
			creating = false;
		}
	}

	async function deleteVolume(id: string, name: string) {
		if (!confirm(`볼륨 "${name || id.slice(0, 8)}"을 삭제하시겠습니까?`)) return;
		deleting = id;
		try {
			await api.delete(`/api/volumes/${id}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
			await fetchVolumes();
		} catch (e) {
			alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			deleting = null;
		}
	}

	async function createShare() {
		if (!shareForm.name.trim() || shareForm.size_gb < 1) return;
		creating = true;
		createError = '';
		try {
			await api.post('/api/shares', shareForm, $auth.token ?? undefined, $auth.projectId ?? undefined);
			showShareModal = false;
			shareForm = { name: '', size_gb: 50 };
			await fetchShares();
		} catch (e) {
			createError = e instanceof ApiError ? e.message : '생성 실패';
		} finally {
			creating = false;
		}
	}

	async function deleteShare(id: string, name: string) {
		if (!confirm(`Share "${name || id.slice(0, 8)}"을 삭제하시겠습니까?`)) return;
		deleting = id;
		try {
			await api.delete(`/api/shares/${id}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
			await fetchShares();
		} catch (e) {
			alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			deleting = null;
		}
	}

	async function createNetwork() {
		if (!netForm.name.trim()) return;
		creating = true;
		createError = '';
		try {
			const net = await api.post<Network>('/api/networks', { name: netForm.name }, $auth.token ?? undefined, $auth.projectId ?? undefined);
			if (netForm.addSubnet && netForm.cidr.trim()) {
				await api.post(`/api/networks/${net.id}/subnets`, {
					name: netForm.subnetName || `${netForm.name}-subnet`,
					cidr: netForm.cidr,
					gateway_ip: netForm.gateway || null,
					enable_dhcp: netForm.dhcp,
				}, $auth.token ?? undefined, $auth.projectId ?? undefined);
			}
			showNetworkModal = false;
			netForm = { name: '', addSubnet: false, subnetName: '', cidr: '10.0.0.0/24', gateway: '', dhcp: true };
			await fetchNetworks();
		} catch (e) {
			createError = e instanceof ApiError ? e.message : '생성 실패';
		} finally {
			creating = false;
		}
	}

	async function deleteNetwork(id: string, name: string) {
		if (!confirm(`네트워크 "${name || id.slice(0, 8)}"을 삭제하시겠습니까?`)) return;
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

	async function createRouter() {
		if (!routerForm.name.trim()) return;
		creating = true;
		createError = '';
		try {
			await api.post('/api/routers', {
				name: routerForm.name,
				external_network_id: routerForm.external_network_id || null,
			}, $auth.token ?? undefined, $auth.projectId ?? undefined);
			showRouterModal = false;
			routerForm = { name: '', external_network_id: '' };
			await fetchRouters();
		} catch (e) {
			createError = e instanceof ApiError ? e.message : '생성 실패';
		} finally {
			creating = false;
		}
	}

	function openModal(tab: Tab) {
		createError = '';
		if (tab === 'volumes') showVolumeModal = true;
		else if (tab === 'shares') showShareModal = true;
		else if (tab === 'networks') showNetworkModal = true;
		else if (tab === 'routers') showRouterModal = true;
	}

	function closeModal() {
		showVolumeModal = false;
		showShareModal = false;
		showNetworkModal = false;
		showRouterModal = false;
		createError = '';
	}

	$effect(() => {
		const projectId = $auth.projectId;
		if (!projectId) return;

		loading = true;
		loadConfig().then(() => {
			fetchAllData();
			const interval = setInterval(fetchAllData, refreshIntervalMs);
			return () => clearInterval(interval);
		});
	});

	const statusColor: Record<string, string> = {
		ACTIVE:    'text-green-400 bg-green-900/30',
		BUILD:     'text-yellow-400 bg-yellow-900/30',
		SHUTOFF:   'text-gray-400 bg-gray-800',
		ERROR:     'text-red-400 bg-red-900/30',
		DELETING:  'text-orange-400 bg-orange-900/30',
		available: 'text-green-400 bg-green-900/30',
		creating:  'text-yellow-400 bg-yellow-900/30',
		deleting:  'text-orange-400 bg-orange-900/30',
		error:     'text-red-400 bg-red-900/30',
		ACTIVE_STANDALONE: 'text-green-400 bg-green-900/30',
		DOWN:      'text-red-400 bg-red-900/30',
	};

	const strategyLabel: Record<string, string> = {
		prebuilt: '사전 빌드',
		dynamic:  '동적 생성',
	};

</script>

<!-- 생성 모달 -->
{#if showVolumeModal || showShareModal || showNetworkModal || showRouterModal}
	<div
		class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
		onclick={closeModal}
		onkeydown={(e) => e.key === 'Escape' && closeModal()}
		role="dialog"
		aria-modal="true"
		tabindex="-1"
	>
		<div
			class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl"
			onclick={(e) => e.stopPropagation()}
			onkeydown={(e) => e.stopPropagation()}
			role="document"
		>
			{#if showVolumeModal}
				<h2 class="text-lg font-semibold text-white mb-5">볼륨 생성</h2>
				<div class="space-y-4">
					<div>
						<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름</label>
						<input
							bind:value={volForm.name}
							type="text"
							placeholder="my-volume"
							class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
						/>
					</div>
					<div>
						<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">크기 (GB)</label>
						<input
							bind:value={volForm.size_gb}
							type="number"
							min="1"
							class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
						/>
					</div>
				</div>

			{:else if showShareModal}
				<h2 class="text-lg font-semibold text-white mb-5">Share 생성</h2>
				<div class="space-y-4">
					<div>
						<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름</label>
						<input
							bind:value={shareForm.name}
							type="text"
							placeholder="my-share"
							class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
						/>
					</div>
					<div>
						<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">크기 (GB)</label>
						<input
							bind:value={shareForm.size_gb}
							type="number"
							min="1"
							class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
						/>
					</div>
				</div>

			{:else if showRouterModal}
				<h2 class="text-lg font-semibold text-white mb-5">라우터 생성</h2>
				<div class="space-y-4">
					<div>
						<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름</label>
						<input
							bind:value={routerForm.name}
							type="text"
							placeholder="my-router"
							class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
						/>
					</div>
					<div>
						<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">외부 네트워크 (선택)</label>
						<select
							bind:value={routerForm.external_network_id}
							class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
						>
							<option value="">없음</option>
							{#each networks.filter(n => n.is_external) as extNet}
								<option value={extNet.id}>{extNet.name}</option>
							{/each}
						</select>
					</div>
				</div>

			{:else if showNetworkModal}
				<h2 class="text-lg font-semibold text-white mb-5">네트워크 생성</h2>
				<div class="space-y-4">
					<div>
						<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">네트워크 이름</label>
						<input
							bind:value={netForm.name}
							type="text"
							placeholder="my-network"
							class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
						/>
					</div>
					<div class="flex items-center gap-2">
						<input type="checkbox" id="add-subnet" bind:checked={netForm.addSubnet} class="rounded border-gray-600" />
						<label for="add-subnet" class="text-sm text-gray-300">서브넷 추가</label>
					</div>
					{#if netForm.addSubnet}
						<div class="pl-4 border-l border-gray-700 space-y-3">
							<div>
								<label class="block text-xs text-gray-400 mb-1 uppercase tracking-wide">서브넷 이름 (선택)</label>
								<input
									bind:value={netForm.subnetName}
									type="text"
									placeholder="my-subnet"
									class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
								/>
							</div>
							<div>
								<label class="block text-xs text-gray-400 mb-1 uppercase tracking-wide">CIDR</label>
								<input
									bind:value={netForm.cidr}
									type="text"
									placeholder="10.0.0.0/24"
									class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 font-mono"
								/>
							</div>
							<div>
								<label class="block text-xs text-gray-400 mb-1 uppercase tracking-wide">게이트웨이 (선택)</label>
								<input
									bind:value={netForm.gateway}
									type="text"
									placeholder="10.0.0.1"
									class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 font-mono"
								/>
							</div>
							<div class="flex items-center gap-2">
								<input type="checkbox" id="net-dhcp" bind:checked={netForm.dhcp} class="rounded border-gray-600" />
								<label for="net-dhcp" class="text-sm text-gray-300">DHCP 활성화</label>
							</div>
						</div>
					{/if}
				</div>
			{/if}

			{#if createError}
				<div class="mt-4 text-red-400 text-xs bg-red-900/20 border border-red-800 rounded px-3 py-2">{createError}</div>
			{/if}

			<div class="flex justify-end gap-3 mt-6">
				<button
					onclick={closeModal}
					class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors"
				>
					취소
				</button>
				<button
					onclick={() => {
						if (showVolumeModal) createVolume();
						else if (showShareModal) createShare();
						else if (showRouterModal) createRouter();
						else createNetwork();
					}}
					disabled={creating}
					class="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors"
				>
					{creating ? '생성 중...' : '생성'}
				</button>
			</div>
		</div>
	</div>
{/if}

<div class="p-8">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-white">대시보드</h1>
		<div class="flex items-center gap-2">
			{#if activeTab !== 'instances' && activeTab !== 'loadbalancers'}
				<button
					onclick={() => openModal(activeTab)}
					class="bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
				>
					+ {tabLabels[activeTab]} 생성
				</button>
			{:else if activeTab === 'loadbalancers'}
				<button
					onclick={() => goto('/dashboard/loadbalancers/new')}
					class="bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
				>
					+ 로드밸런서 생성
				</button>
			{/if}
			<a
				href="/create"
				class="bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
			>
				+ VM 생성
			</a>
		</div>
	</div>

	<!-- 리소스 모니터링 카드 -->
	{#if summary}
		{@const c = summary.compute}
		{@const s = summary.storage}
		<div class="grid grid-cols-2 gap-3 mb-6 lg:grid-cols-6">
			<!-- 인스턴스 -->
			<div class="bg-gray-900 border border-gray-800 rounded-lg p-4">
				<div class="text-xs text-gray-500 uppercase tracking-wide mb-2">인스턴스</div>
				<div class="text-2xl font-bold text-white mb-1">{summary.instances.active}<span class="text-base text-gray-500">/{summary.instances.total}</span></div>
				<div class="flex gap-2 text-xs">
					<span class="text-green-400">{summary.instances.active} active</span>
					{#if summary.instances.shutoff > 0}<span class="text-gray-500">{summary.instances.shutoff} off</span>{/if}
					{#if summary.instances.error > 0}<span class="text-red-400">{summary.instances.error} err</span>{/if}
				</div>
			</div>
			<!-- vCPU -->
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
			<!-- RAM -->
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
			<!-- GPU -->
			<div class="bg-gray-900 border border-gray-800 rounded-lg p-4">
				<div class="text-xs text-gray-500 uppercase tracking-wide mb-2">GPU (활성)</div>
				<div class="text-2xl font-bold {summary.gpu_used > 0 ? 'text-purple-300' : 'text-white'} mb-1">{summary.gpu_used}</div>
				<div class="text-xs text-gray-500">GPU 사용 인스턴스</div>
			</div>
			<!-- 볼륨 -->
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
			<!-- 스토리지 -->
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

	<!-- 탭 바 -->
	<div class="flex gap-0 mb-6 border-b border-gray-800">
		{#each (['instances', 'volumes', 'shares', 'networks', 'routers', 'loadbalancers'] as Tab[]) as tab}
			<button
				onclick={() => (activeTab = tab)}
				class="px-4 py-2.5 text-sm transition-colors border-b-2 -mb-px
					{activeTab === tab
						? 'text-white border-blue-500'
						: 'text-gray-400 hover:text-gray-200 border-transparent'}"
			>
				{tabLabels[tab]}
				<span class="ml-1.5 text-xs px-1.5 py-0.5 rounded-full
					{activeTab === tab ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400'}">
					{tabCount(tab)}
				</span>
			</button>
		{/each}
	</div>

	<!-- 인스턴스 탭 -->
	{#if activeTab === 'instances'}
		{#if instancesError}
			<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">
				{instancesError}
			</div>
		{/if}
		{#if loading}
			<LoadingSkeleton variant="table" rows={5} />
		{:else if instances.length === 0}
			<div class="text-center py-20 text-gray-600">
				<div class="text-5xl mb-4">☁️</div>
				<p class="text-lg">인스턴스가 없습니다</p>
				<a href="/create" class="text-blue-400 hover:text-blue-300 text-sm mt-2 inline-block">
					첫 VM을 생성하세요 →
				</a>
			</div>
		{:else}
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
							<th class="text-left py-3 pr-6">이름</th>
							<th class="text-left py-3 pr-6">상태</th>
							<th class="text-left py-3 pr-6">이미지 / 플레이버</th>
							<th class="text-left py-3 pr-6">IP</th>
							<th class="text-left py-3 pr-6">라이브러리</th>
							<th class="text-left py-3 pr-6">전략</th>
							<th class="text-right py-3">액션</th>
						</tr>
					</thead>
					<tbody>
						{#each instances as inst (inst.id)}
							<tr
								onclick={() => goto('/dashboard/instances/' + inst.id)}
								class="border-b border-gray-800/50 hover:bg-gray-800/50 transition-colors cursor-pointer"
							>
								<td class="py-3 pr-6 font-medium text-white">{inst.name}</td>
								<td class="py-3 pr-6">
									<span class="px-2 py-0.5 rounded text-xs font-medium {statusColor[inst.status] ?? 'text-gray-400 bg-gray-800'}">
										{inst.status}
									</span>
								</td>
								<td class="py-3 pr-6 text-xs text-gray-400">
									<div>{inst.image_name ?? '-'}</div>
									{#if inst.flavor_name}
										<div class="text-gray-600 mt-0.5">{inst.flavor_name}</div>
									{/if}
								</td>
								<td class="py-3 pr-6 text-xs">
									{#if inst.ip_addresses.length > 0}
										{@const fixedIps = inst.ip_addresses.filter(ip => ip.type === 'fixed')}
										{@const floatingIps = inst.ip_addresses.filter(ip => ip.type === 'floating')}
										<div class="flex flex-col gap-0.5">
											{#each fixedIps as fip}
												{@const paired = floatingIps.find(fl => fl.network_name === fip.network_name)}
												<div class="flex items-center gap-1.5 flex-wrap">
													<span class="font-mono text-gray-400">{fip.addr}</span>
													{#if paired}
														<span class="font-mono text-green-400 bg-green-900/20 px-1.5 py-0.5 rounded">{paired.addr}</span>
													{/if}
													<span class="text-gray-600">{fip.network_name}</span>
												</div>
											{/each}
											{#each floatingIps.filter(fl => !fixedIps.some(f => f.network_name === fl.network_name)) as fl}
												<div class="flex items-center gap-1.5">
													<span class="font-mono text-green-400 bg-green-900/20 px-1.5 py-0.5 rounded">{fl.addr}</span>
													<span class="text-gray-600">{fl.network_name}</span>
												</div>
											{/each}
										</div>
									{:else}
										<span class="text-gray-600">-</span>
									{/if}
								</td>
								<td class="py-3 pr-6">
									<div class="flex flex-wrap gap-1">
										{#each inst.union_libraries.filter(Boolean) as lib}
											<span class="px-1.5 py-0.5 bg-blue-900/40 text-blue-300 rounded text-xs">{lib}</span>
										{/each}
									</div>
								</td>
								<td class="py-3 pr-6 text-gray-500 text-xs">
									{inst.union_strategy ? strategyLabel[inst.union_strategy] ?? inst.union_strategy : '-'}
								</td>
								<td class="py-3 text-right">
									<div class="flex items-center justify-end gap-2">
										{#if inst.status === 'ACTIVE'}
											<button
												onclick={(e) => { e.stopPropagation(); openConsole(inst.id); }}
												class="text-gray-400 hover:text-white text-xs px-2 py-1 rounded border border-gray-700 hover:border-gray-500 transition-colors"
											>
												콘솔
											</button>
										{/if}
										<button
											onclick={(e) => { e.stopPropagation(); deleteInstance(inst.id, inst.name); }}
											disabled={deleting === inst.id}
											class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-1 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors"
										>
											{deleting === inst.id ? '삭제 중...' : '삭제'}
										</button>
									</div>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}

	<!-- 볼륨 탭 -->
	{:else if activeTab === 'volumes'}
		{#if volumesError}
			<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">
				{volumesError}
			</div>
		{/if}
		{#if loading}
			<LoadingSkeleton variant="table" rows={5} />
		{:else if volumes.length === 0}
			<div class="text-center py-20 text-gray-600">
				<div class="text-5xl mb-4">💾</div>
				<p class="text-lg">볼륨이 없습니다</p>
				<button onclick={() => openModal('volumes')} class="text-blue-400 hover:text-blue-300 text-sm mt-2 inline-block">
					첫 볼륨을 생성하세요 →
				</button>
			</div>
		{:else}
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
							<th class="text-left py-3 pr-6">이름</th>
							<th class="text-left py-3 pr-6">상태</th>
							<th class="text-left py-3 pr-6">크기</th>
							<th class="text-left py-3 pr-6">타입</th>
							<th class="text-left py-3 pr-6">연결된 인스턴스</th>
							<th class="text-right py-3">액션</th>
						</tr>
					</thead>
					<tbody>
						{#each volumes as vol (vol.id)}
							<tr
								onclick={() => goto('/dashboard/volumes/' + vol.id)}
								class="border-b border-gray-800/50 hover:bg-gray-800/50 transition-colors cursor-pointer"
							>
								<td class="py-3 pr-6 font-medium">
									{#if vol.name}
										<span class="text-white">{vol.name}</span>
									{:else}
										<span class="text-gray-400 font-mono text-xs">{vol.id}</span>
									{/if}
								</td>
								<td class="py-3 pr-6">
									<span class="px-2 py-0.5 rounded text-xs font-medium {statusColor[vol.status] ?? 'text-gray-400 bg-gray-800'}">
										{vol.status}
									</span>
								</td>
								<td class="py-3 pr-6 text-gray-400">{vol.size} GB</td>
								<td class="py-3 pr-6 text-gray-400 text-xs">{vol.volume_type ?? '-'}</td>
								<td class="py-3 pr-6 text-xs">
									{#if vol.attachments.length > 0}
										<div class="flex flex-wrap gap-1">
											{#each vol.attachments as a}
												{@const serverId = (a as Record<string, string>).server_id}
												{@const serverName = instanceNameMap.get(serverId)}
												<a
													href="/dashboard/instances/{serverId}"
													onclick={(e) => e.stopPropagation()}
													class="text-blue-400 hover:text-blue-300 transition-colors"
												>
													{serverName ?? serverId?.slice(0, 8) + '…'}
												</a>
											{/each}
										</div>
									{:else}
										<span class="text-gray-500">미연결</span>
									{/if}
								</td>
								<td class="py-3 text-right">
									<button
										onclick={(e) => { e.stopPropagation(); deleteVolume(vol.id, vol.name); }}
										disabled={deleting === vol.id || vol.attachments.length > 0}
										class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-1 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors"
										title={vol.attachments.length > 0 ? '연결된 볼륨은 삭제할 수 없습니다' : ''}
									>
										{deleting === vol.id ? '삭제 중...' : '삭제'}
									</button>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}

	<!-- 공유(Share) 탭 -->
	{:else if activeTab === 'shares'}
		{#if sharesError}
			<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">
				{sharesError}
			</div>
		{/if}
		{#if loading}
			<LoadingSkeleton variant="table" rows={5} />
		{:else if shares.length === 0}
			<div class="text-center py-20 text-gray-600">
				<div class="text-5xl mb-4">📂</div>
				<p class="text-lg">공유(Share)가 없습니다</p>
				<button onclick={() => openModal('shares')} class="text-blue-400 hover:text-blue-300 text-sm mt-2 inline-block">
					첫 Share를 생성하세요 →
				</button>
			</div>
		{:else}
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
							<th class="text-left py-3 pr-6">이름</th>
							<th class="text-left py-3 pr-6">상태</th>
							<th class="text-left py-3 pr-6">크기</th>
							<th class="text-left py-3 pr-6">프로토콜</th>
							<th class="text-left py-3 pr-6">라이브러리</th>
							<th class="text-left py-3 pr-6">버전</th>
							<th class="text-right py-3">액션</th>
						</tr>
					</thead>
					<tbody>
						{#each shares as share (share.id)}
							<tr
								onclick={() => goto('/dashboard/shares/' + share.id)}
								class="border-b border-gray-800/50 hover:bg-gray-800/50 transition-colors cursor-pointer"
							>
								<td class="py-3 pr-6 font-medium text-white">{share.name || '-'}</td>
								<td class="py-3 pr-6">
									<span class="px-2 py-0.5 rounded text-xs font-medium {statusColor[share.status] ?? 'text-gray-400 bg-gray-800'}">
										{share.status}
									</span>
								</td>
								<td class="py-3 pr-6 text-gray-400">{share.size} GB</td>
								<td class="py-3 pr-6">
									<span class="px-1.5 py-0.5 bg-purple-900/40 text-purple-300 rounded text-xs">{share.share_proto}</span>
								</td>
								<td class="py-3 pr-6 text-gray-400 text-xs">{share.library_name ?? '-'}</td>
								<td class="py-3 pr-6 text-gray-500 text-xs">{share.library_version ?? '-'}</td>
								<td class="py-3 text-right">
									<button
										onclick={(e) => { e.stopPropagation(); deleteShare(share.id, share.name); }}
										disabled={deleting === share.id}
										class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-1 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors"
									>
										{deleting === share.id ? '삭제 중...' : '삭제'}
									</button>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}

	<!-- 네트워크 탭 -->
	{:else if activeTab === 'networks'}
		{#if networksError}
			<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">
				{networksError}
			</div>
		{/if}
		{#if loading}
			<LoadingSkeleton variant="table" rows={5} />
		{:else if networks.length === 0}
			<div class="text-center py-20 text-gray-600">
				<div class="text-5xl mb-4">🌐</div>
				<p class="text-lg">네트워크가 없습니다</p>
				<button onclick={() => openModal('networks')} class="text-blue-400 hover:text-blue-300 text-sm mt-2 inline-block">
					첫 네트워크를 생성하세요 →
				</button>
			</div>
		{:else}
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
							<th class="text-left py-3 pr-6">이름</th>
							<th class="text-left py-3 pr-6">상태</th>
							<th class="text-left py-3 pr-6">서브넷 수</th>
							<th class="text-left py-3 pr-6">외부</th>
							<th class="text-left py-3 pr-6">공유</th>
							<th class="text-right py-3">액션</th>
						</tr>
					</thead>
					<tbody>
						{#each networks as net (net.id)}
							<tr
								onclick={() => goto('/dashboard/networks/' + net.id)}
								class="border-b border-gray-800/50 hover:bg-gray-800/50 transition-colors cursor-pointer"
							>
								<td class="py-3 pr-6 font-medium text-white">{net.name || '-'}</td>
								<td class="py-3 pr-6">
									<span class="px-2 py-0.5 rounded text-xs font-medium {statusColor[net.status] ?? 'text-gray-400 bg-gray-800'}">
										{net.status}
									</span>
								</td>
								<td class="py-3 pr-6 text-gray-400">{net.subnets.length}</td>
								<td class="py-3 pr-6">
									{#if net.is_external}
										<span class="px-1.5 py-0.5 bg-orange-900/40 text-orange-300 rounded text-xs">외부</span>
									{:else}
										<span class="text-gray-600 text-xs">-</span>
									{/if}
								</td>
								<td class="py-3 pr-6">
									{#if net.is_shared}
										<span class="px-1.5 py-0.5 bg-teal-900/40 text-teal-300 rounded text-xs">공유</span>
									{:else}
										<span class="text-gray-600 text-xs">-</span>
									{/if}
								</td>
								<td class="py-3 text-right">
									<button
										onclick={(e) => { e.stopPropagation(); deleteNetwork(net.id, net.name); }}
										disabled={deleting === net.id || net.is_external || net.is_shared}
										class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-1 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors"
										title={net.is_external ? '외부 네트워크는 삭제할 수 없습니다' : net.is_shared ? '공유 네트워크는 삭제할 수 없습니다' : ''}
									>
										{deleting === net.id ? '삭제 중...' : '삭제'}
									</button>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}

	<!-- 라우터 탭 -->
	{:else if activeTab === 'routers'}
		{#if routersError}
			<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{routersError}</div>
		{/if}
		{#if loading}
			<LoadingSkeleton variant="table" rows={5} />
		{:else if routers.length === 0}
			<div class="text-center py-20 text-gray-600">
				<div class="text-5xl mb-4">🔀</div>
				<p class="text-lg">라우터가 없습니다</p>
				<button onclick={() => openModal('routers')} class="text-blue-400 hover:text-blue-300 text-sm mt-2 inline-block">
					라우터 생성 →
				</button>
			</div>
		{:else}
			<div class="overflow-x-auto">
				<table class="w-full text-sm text-gray-300">
					<thead>
						<tr class="border-b border-gray-700 text-gray-500 text-xs uppercase tracking-wide">
							<th class="text-left py-3 pr-6">이름</th>
							<th class="text-left py-3 pr-6">상태</th>
							<th class="text-left py-3 pr-6">외부 게이트웨이</th>
							<th class="text-left py-3 pr-6">연결된 서브넷 수</th>
							<th class="text-right py-3">상세</th>
						</tr>
					</thead>
					<tbody>
						{#each routers as router (router.id)}
							<tr
								onclick={() => goto('/dashboard/routers/' + router.id)}
								class="border-b border-gray-800/50 hover:bg-gray-800/50 transition-colors cursor-pointer"
							>
								<td class="py-3 pr-6 font-medium text-white">{router.name || router.id.slice(0, 8)}</td>
								<td class="py-3 pr-6">
									<span class="px-2 py-0.5 rounded text-xs font-medium {router.status === 'ACTIVE' ? 'text-green-400 bg-green-900/30' : 'text-gray-400 bg-gray-800'}">
										{router.status}
									</span>
								</td>
								<td class="py-3 pr-6 text-gray-400 text-xs font-mono">
									{router.external_gateway_network_id ? router.external_gateway_network_id.slice(0, 12) + '…' : '-'}
								</td>
								<td class="py-3 pr-6 text-gray-400">{router.connected_subnet_ids.length}</td>
								<td class="py-3 text-right">
									<button
										onclick={(e) => { e.stopPropagation(); goto('/dashboard/routers/' + router.id); }}
										class="text-blue-400 hover:text-blue-300 text-xs px-2 py-1 rounded border border-blue-900 hover:border-blue-700 transition-colors"
									>상세</button>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}

	<!-- 로드밸런서 탭 -->
	{:else if activeTab === 'loadbalancers'}
		{#if loading}
			<LoadingSkeleton variant="table" rows={5} />
		{:else if loadBalancers.length === 0}
			<div class="text-center py-20 text-gray-600">
				<div class="text-5xl mb-4">⚖️</div>
				<p class="text-lg">로드밸런서가 없습니다</p>
				<button onclick={() => goto('/dashboard/loadbalancers/new')} class="text-blue-400 hover:text-blue-300 text-sm mt-2 inline-block">
					로드밸런서 생성 →
				</button>
			</div>
		{:else}
			<div class="overflow-x-auto">
				<table class="w-full text-sm text-gray-300">
					<thead>
						<tr class="border-b border-gray-700 text-gray-500 text-xs uppercase tracking-wide">
							<th class="text-left py-3 pr-6">이름</th>
							<th class="text-left py-3 pr-6">프로비저닝 상태</th>
							<th class="text-left py-3 pr-6">운영 상태</th>
							<th class="text-left py-3 pr-6">VIP 주소</th>
							<th class="text-right py-3">상세</th>
						</tr>
					</thead>
					<tbody>
						{#each loadBalancers as lb (lb.id)}
							<tr
								onclick={() => goto('/dashboard/loadbalancers/' + lb.id)}
								class="border-b border-gray-800/50 hover:bg-gray-800/50 transition-colors cursor-pointer"
							>
								<td class="py-3 pr-6 font-medium text-white">{lb.name || lb.id.slice(0, 8)}</td>
								<td class="py-3 pr-6">
									<span class="px-2 py-0.5 rounded text-xs font-medium {lb.status === 'ACTIVE' ? 'text-green-400 bg-green-900/30' : 'text-yellow-400 bg-yellow-900/30'}">
										{lb.status}
									</span>
								</td>
								<td class="py-3 pr-6">
									<span class="px-2 py-0.5 rounded text-xs {lb.operating_status === 'ONLINE' ? 'text-green-400' : 'text-gray-400'}">
										{lb.operating_status}
									</span>
								</td>
								<td class="py-3 pr-6 text-gray-400 text-xs font-mono">{lb.vip_address ?? '-'}</td>
								<td class="py-3 text-right">
									<button
										onclick={(e) => { e.stopPropagation(); goto('/dashboard/loadbalancers/' + lb.id); }}
										class="text-blue-400 hover:text-blue-300 text-xs px-2 py-1 rounded border border-blue-900 hover:border-blue-700 transition-colors"
									>상세</button>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	{/if}
</div>
