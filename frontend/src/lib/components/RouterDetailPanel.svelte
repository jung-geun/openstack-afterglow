<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import { goto } from '$app/navigation';

	interface RouterInterface {
		id: string;
		subnet_id: string;
		subnet_name: string;
		network_id: string;
		ip_address: string;
	}

	interface RouterDetail {
		id: string;
		name: string;
		status: string;
		project_id: string | null;
		external_gateway_network_id: string | null;
		external_gateway_network_name: string | null;
		interfaces: RouterInterface[];
	}

	interface Network {
		id: string;
		name: string;
		is_external: boolean;
		is_shared: boolean;
		subnets: string[];
	}

	interface Subnet {
		id: string;
		name: string;
		cidr: string;
		network_id: string;
	}

	let { routerId, onClose, onDeleted }: { routerId: string; onClose?: () => void; onDeleted?: () => void } = $props();

	let router = $state<RouterDetail | null>(null);
	let loading = $state(true);
	let error = $state('');
	let saving = $state(false);

	let showAddInterface = $state(false);
	let availableNetworks = $state<Network[]>([]);
	let externalNetworks = $state<Network[]>([]);
	let selectedNetId = $state('');
	let allSubnets = $state<Subnet[]>([]);
	let selectedSubnetId = $state('');
	let showSetGateway = $state(false);
	let selectedExtNetId = $state('');

	async function fetchRouter() {
		loading = true;
		error = '';
		try {
			router = await api.get<RouterDetail>(`/api/routers/${routerId}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
		} catch (e) {
			error = e instanceof ApiError ? e.message : '라우터 조회 실패';
		} finally {
			loading = false;
		}
	}

	async function fetchNetworks() {
		try {
			const nets = await api.get<Network[]>('/api/networks', $auth.token ?? undefined, $auth.projectId ?? undefined);
			availableNetworks = nets.filter(n => !n.is_external);
			externalNetworks = nets.filter(n => n.is_external);
		} catch { /* 무시 */ }
	}

	$effect(() => {
		if (routerId && $auth.projectId) {
			fetchRouter();
			fetchNetworks();
		}
	});

	$effect(() => {
		if (!selectedNetId) { allSubnets = []; selectedSubnetId = ''; return; }
		api.get<{ subnet_details: Subnet[] }>(`/api/networks/${selectedNetId}`, $auth.token ?? undefined, $auth.projectId ?? undefined)
			.then(d => { allSubnets = d.subnet_details ?? []; selectedSubnetId = allSubnets[0]?.id ?? ''; })
			.catch(() => {});
	});

	async function addInterface() {
		if (!selectedSubnetId) return;
		saving = true;
		try {
			await api.post(`/api/routers/${routerId}/interfaces`, { subnet_id: selectedSubnetId }, $auth.token ?? undefined, $auth.projectId ?? undefined);
			showAddInterface = false;
			selectedNetId = '';
			selectedSubnetId = '';
			await fetchRouter();
		} catch (e) {
			alert('인터페이스 추가 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			saving = false;
		}
	}

	async function removeInterface(subnetId: string) {
		if (!confirm('인터페이스를 제거하시겠습니까?')) return;
		saving = true;
		try {
			await api.delete(`/api/routers/${routerId}/interfaces/${subnetId}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
			await fetchRouter();
		} catch (e) {
			alert('인터페이스 제거 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			saving = false;
		}
	}

	async function setGateway() {
		if (!selectedExtNetId) return;
		saving = true;
		try {
			await api.post(`/api/routers/${routerId}/gateway`, { external_network_id: selectedExtNetId }, $auth.token ?? undefined, $auth.projectId ?? undefined);
			showSetGateway = false;
			selectedExtNetId = '';
			await fetchRouter();
		} catch (e) {
			alert('게이트웨이 설정 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			saving = false;
		}
	}

	async function removeGateway() {
		if (!confirm('외부 게이트웨이를 제거하시겠습니까?')) return;
		saving = true;
		try {
			await api.delete(`/api/routers/${routerId}/gateway`, $auth.token ?? undefined, $auth.projectId ?? undefined);
			await fetchRouter();
		} catch (e) {
			alert('게이트웨이 제거 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			saving = false;
		}
	}

	async function deleteRouter() {
		if (!confirm(`라우터 "${router?.name || routerId}"을 삭제하시겠습니까?`)) return;
		saving = true;
		try {
			await api.delete(`/api/routers/${routerId}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
			if (onDeleted) {
				onDeleted();
			} else {
				onClose?.();
				goto('/dashboard/network/routers');
			}
		} catch (e) {
			alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
			saving = false;
		}
	}
</script>

<div class="p-6 text-gray-100">
	<!-- 헤더 -->
	<div class="flex items-center justify-between mb-6 border-b border-gray-800 pb-4">
		<h2 class="text-xl font-bold text-white">라우터 상세</h2>
		<div class="flex items-center gap-2">
			<button
				onclick={() => goto(`/dashboard/network/routers/${routerId}`)}
				class="text-xs text-gray-400 hover:text-blue-300 px-2 py-1 rounded border border-gray-700 hover:border-blue-700 transition-colors"
			>전체 보기 →</button>
			{#if onClose}
				<button onclick={onClose} class="text-gray-400 hover:text-white text-xl leading-none px-2">✕</button>
			{/if}
		</div>
	</div>

	{#if loading}
		<div class="text-gray-500 text-sm">불러오는 중...</div>
	{:else if error}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">{error}</div>
	{:else if router}
		<!-- 기본 정보 -->
		<div class="flex items-start justify-between mb-6">
			<div>
				<h3 class="text-lg font-semibold text-white">{router.name || router.id.slice(0, 12)}</h3>
				<div class="flex items-center gap-3 mt-2">
					<span class="px-2 py-0.5 rounded text-xs font-medium {router.status === 'ACTIVE' ? 'text-green-400 bg-green-900/30' : 'text-gray-400 bg-gray-800'}">
						{router.status}
					</span>
					<span class="text-xs text-gray-500 font-mono">{router.id}</span>
				</div>
			</div>
			<button
				onclick={deleteRouter}
				disabled={saving}
				class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors"
			>삭제</button>
		</div>

		<!-- 외부 게이트웨이 -->
		<section class="bg-gray-900 border border-gray-800 rounded-lg p-5 mb-4">
			<div class="flex items-center justify-between mb-3">
				<h4 class="font-semibold text-white text-sm">외부 게이트웨이</h4>
				<div class="flex gap-2">
					{#if router.external_gateway_network_id}
						<button
							onclick={removeGateway}
							disabled={saving}
							class="text-red-400 hover:text-red-300 text-xs px-2 py-1 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors"
						>게이트웨이 제거</button>
					{:else}
						<button
							onclick={() => showSetGateway = !showSetGateway}
							class="text-blue-400 hover:text-blue-300 text-xs px-2 py-1 rounded border border-blue-900 hover:border-blue-700 transition-colors"
						>게이트웨이 설정</button>
					{/if}
				</div>
			</div>

			{#if router.external_gateway_network_id}
				<div class="text-sm">
					<span class="text-gray-400">네트워크: </span>
					<span class="text-orange-300">{router.external_gateway_network_name || router.external_gateway_network_id}</span>
				</div>
			{:else}
				<p class="text-sm text-gray-600">외부 게이트웨이가 설정되지 않았습니다.</p>
			{/if}

			{#if showSetGateway}
				<div class="mt-4 flex gap-2">
					<select bind:value={selectedExtNetId} class="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200">
						<option value="">외부 네트워크 선택</option>
						{#each externalNetworks as net}
							<option value={net.id}>{net.name || net.id.slice(0, 12)}</option>
						{/each}
					</select>
					<button
						onclick={setGateway}
						disabled={!selectedExtNetId || saving}
						class="bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 text-white text-sm px-3 py-2 rounded transition-colors"
					>설정</button>
					<button onclick={() => showSetGateway = false} class="text-gray-400 hover:text-gray-200 text-sm px-2">취소</button>
				</div>
			{/if}
		</section>

		<!-- 인터페이스 -->
		<section class="bg-gray-900 border border-gray-800 rounded-lg p-5">
			<div class="flex items-center justify-between mb-3">
				<h4 class="font-semibold text-white text-sm">인터페이스 ({router.interfaces.length})</h4>
				<button
					onclick={() => showAddInterface = !showAddInterface}
					class="text-blue-400 hover:text-blue-300 text-xs px-2 py-1 rounded border border-blue-900 hover:border-blue-700 transition-colors"
				>+ 추가</button>
			</div>

			{#if showAddInterface}
				<div class="mb-4 p-4 bg-gray-800/60 border border-gray-700 rounded-lg">
					<div class="flex gap-2 mb-2">
						<select bind:value={selectedNetId} class="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200">
							<option value="">네트워크 선택</option>
							{#each availableNetworks as net}
								<option value={net.id}>{net.name || net.id.slice(0, 12)}</option>
							{/each}
						</select>
						<select bind:value={selectedSubnetId} disabled={!allSubnets.length} class="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 disabled:opacity-50">
							<option value="">서브넷 선택</option>
							{#each allSubnets as subnet}
								<option value={subnet.id}>{subnet.name || subnet.cidr}</option>
							{/each}
						</select>
					</div>
					<div class="flex gap-2">
						<button
							onclick={addInterface}
							disabled={!selectedSubnetId || saving}
							class="bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 text-white text-sm px-3 py-2 rounded transition-colors"
						>추가</button>
						<button onclick={() => { showAddInterface = false; selectedNetId = ''; }} class="text-gray-400 hover:text-gray-200 text-sm px-2">취소</button>
					</div>
				</div>
			{/if}

			{#if router.interfaces.length === 0}
				<p class="text-sm text-gray-600">연결된 인터페이스가 없습니다.</p>
			{:else}
				<div class="space-y-2">
					{#each router.interfaces as iface}
						<div class="flex items-center justify-between bg-gray-800/50 rounded-lg px-4 py-3">
							<div class="text-sm">
								<div class="text-white font-medium">{iface.subnet_name || iface.subnet_id.slice(0, 12)}</div>
								<div class="text-gray-500 text-xs font-mono mt-0.5">{iface.ip_address}</div>
							</div>
							<button
								onclick={() => removeInterface(iface.subnet_id)}
								disabled={saving}
								class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-1 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors"
							>제거</button>
						</div>
					{/each}
				</div>
			{/if}
		</section>
	{/if}
</div>
