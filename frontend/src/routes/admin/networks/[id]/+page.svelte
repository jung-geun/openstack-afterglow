<script lang="ts">
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';

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

	let network = $state<NetworkDetail | null>(null);
	let loading = $state(true);
	let error = $state('');
	let deleting = $state(false);

	// 서브넷 추가
	let showSubnetForm = $state(false);
	let subnetForm = $state({ name: '', cidr: '10.0.0.0/24', gateway: '', dhcp: true });
	let addingSubnet = $state(false);
	let subnetError = $state('');

	// 서브넷 편집
	let editingSubnetId = $state<string | null>(null);
	let editSubnetForm = $state({ name: '', gateway: '', dhcp: true });
	let savingSubnet = $state(false);
	let editSubnetError = $state('');

	// 서브넷 삭제
	let deletingSubnetId = $state<string | null>(null);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	const statusColor: Record<string, string> = {
		ACTIVE: 'text-green-400 bg-green-900/30',
		DOWN: 'text-red-400 bg-red-900/30',
		BUILD: 'text-yellow-400 bg-yellow-900/30',
	};

	$effect(() => {
		const id = $page.params.id;
		if (!id || !$auth.token) return;
		fetchNetwork(id);
	});

	async function fetchNetwork(id: string) {
		loading = true;
		error = '';
		try {
			network = await api.get<NetworkDetail>(`/api/admin/networks/${id}`, token, projectId);
		} catch (e) {
			error = e instanceof ApiError ? `조회 실패 (${e.status}): ${e.message}` : '서버 오류';
		} finally {
			loading = false;
		}
	}

	async function deleteNetwork() {
		if (!network) return;
		if (!confirm(`네트워크 "${network.name || network.id}"를 삭제하시겠습니까?`)) return;
		deleting = true;
		try {
			await api.delete(`/api/admin/networks/${network.id}`, token, projectId);
			goto('/admin/networks');
		} catch (e) {
			alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			deleting = false;
		}
	}

	function startEditSubnet(subnet: SubnetDetail) {
		editingSubnetId = subnet.id;
		editSubnetForm = {
			name: subnet.name || '',
			gateway: subnet.gateway_ip ?? '',
			dhcp: subnet.dhcp_enabled,
		};
		editSubnetError = '';
	}

	async function saveSubnet() {
		if (!editingSubnetId) return;
		savingSubnet = true;
		editSubnetError = '';
		try {
			await api.put(
				`/api/networks/subnets/${editingSubnetId}`,
				{
					name: editSubnetForm.name || null,
					gateway_ip: editSubnetForm.gateway || null,
					enable_dhcp: editSubnetForm.dhcp,
				},
				token, projectId
			);
			editingSubnetId = null;
			await fetchNetwork(network!.id);
		} catch (e) {
			editSubnetError = e instanceof ApiError ? e.message : '서브넷 업데이트 실패';
		} finally {
			savingSubnet = false;
		}
	}

	async function addSubnet() {
		if (!network || !subnetForm.cidr.trim()) return;
		addingSubnet = true;
		subnetError = '';
		try {
			await api.post(
				`/api/networks/${network.id}/subnets`,
				{
					name: subnetForm.name || `${network.name}-subnet`,
					cidr: subnetForm.cidr,
					gateway_ip: subnetForm.gateway || null,
					enable_dhcp: subnetForm.dhcp,
				},
				token, projectId
			);
			showSubnetForm = false;
			subnetForm = { name: '', cidr: '10.0.0.0/24', gateway: '', dhcp: true };
			await fetchNetwork(network.id);
		} catch (e) {
			subnetError = e instanceof ApiError ? e.message : '서브넷 생성 실패';
		} finally {
			addingSubnet = false;
		}
	}

	async function deleteSubnet(subnetId: string, subnetName: string) {
		if (!confirm(`서브넷 "${subnetName || subnetId.slice(0, 8)}"를 삭제하시겠습니까?`)) return;
		deletingSubnetId = subnetId;
		try {
			await api.delete(`/api/networks/subnets/${subnetId}`, token, projectId);
			await fetchNetwork(network!.id);
		} catch (e) {
			alert('서브넷 삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			deletingSubnetId = null;
		}
	}
</script>

<div class="p-4 md:p-8 max-w-5xl mx-auto">
	<div class="mb-6">
		<a href="/admin/networks" class="text-gray-400 hover:text-gray-200 text-sm transition-colors">
			← 네트워크 목록
		</a>
	</div>

	{#if error}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">
			{error}
		</div>
	{:else if loading}
		<LoadingSkeleton variant="card" rows={5} />
	{:else if network}
		<div class="flex items-start justify-between mb-6">
			<div>
				<h1 class="text-2xl font-bold text-white">{network.name || network.id}</h1>
				<div class="flex items-center gap-2 mt-2">
					<span
						class="px-2 py-0.5 rounded text-xs font-medium {statusColor[network.status] ?? 'text-gray-400 bg-gray-800'}"
					>
						{network.status}
					</span>
					{#if network.is_external}
						<span class="px-1.5 py-0.5 bg-orange-900/40 text-orange-300 rounded text-xs">외부</span>
					{/if}
					{#if network.is_shared}
						<span class="px-1.5 py-0.5 bg-teal-900/40 text-teal-300 rounded text-xs">공유</span>
					{/if}
				</div>
			</div>
			<button
				onclick={deleteNetwork}
				disabled={deleting}
				class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors"
			>
				{deleting ? '삭제 중...' : '삭제'}
			</button>
		</div>

		<!-- 기본 정보 -->
		<div class="bg-gray-900 border border-gray-800 rounded-lg p-6 mb-4">
			<h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">기본 정보</h2>
			<dl class="grid grid-cols-2 gap-x-8 gap-y-2">
				<div>
					<dt class="text-xs text-gray-500 mb-0.5">네트워크 ID</dt>
					<dd class="text-sm text-gray-300 font-mono">{network.id}</dd>
				</div>
				<div>
					<dt class="text-xs text-gray-500 mb-0.5">서브넷 수</dt>
					<dd class="text-sm text-gray-300">{network.subnets.length}</dd>
				</div>
				<div>
					<dt class="text-xs text-gray-500 mb-0.5">유형</dt>
					<dd class="text-sm text-gray-300">
						{#if network.is_external}외부{/if}
						{#if network.is_external && network.is_shared} / {/if}
						{#if network.is_shared}공유{/if}
						{#if !network.is_external && !network.is_shared}내부{/if}
					</dd>
				</div>
				<div>
					<dt class="text-xs text-gray-500 mb-0.5">상태</dt>
					<dd class="text-sm text-gray-300">{network.status}</dd>
				</div>
			</dl>
		</div>

		<!-- 서브넷 상세 -->
		<div class="bg-gray-900 border border-gray-800 rounded-lg p-6 mb-4">
			<div class="flex items-center justify-between mb-4">
				<h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide">서브넷</h2>
				<button
					onclick={() => { showSubnetForm = !showSubnetForm; subnetError = ''; }}
					class="text-xs text-blue-400 hover:text-blue-300 transition-colors"
				>
					{showSubnetForm ? '닫기' : '+ 서브넷 추가'}
				</button>
			</div>

			{#if showSubnetForm}
				<div class="mb-4 bg-gray-800 rounded-lg p-4 space-y-3">
					<div class="grid grid-cols-2 gap-3">
						<div>
							<label class="block text-xs text-gray-400 mb-1">이름 (선택)
								<input
									bind:value={subnetForm.name}
									type="text"
									placeholder="my-subnet"
									class="w-full bg-gray-700 border border-gray-600 rounded px-2.5 py-1.5 text-white text-sm focus:outline-none focus:border-blue-500 mt-1"
								/>
							</label>
						</div>
						<div>
							<label class="block text-xs text-gray-400 mb-1">CIDR
								<input
									bind:value={subnetForm.cidr}
									type="text"
									placeholder="10.0.0.0/24"
									class="w-full bg-gray-700 border border-gray-600 rounded px-2.5 py-1.5 text-white text-sm font-mono focus:outline-none focus:border-blue-500 mt-1"
								/>
							</label>
						</div>
						<div>
							<label class="block text-xs text-gray-400 mb-1">게이트웨이 (선택)
								<input
									bind:value={subnetForm.gateway}
									type="text"
									placeholder="10.0.0.1"
									class="w-full bg-gray-700 border border-gray-600 rounded px-2.5 py-1.5 text-white text-sm font-mono focus:outline-none focus:border-blue-500 mt-1"
								/>
							</label>
						</div>
						<div class="flex items-end pb-1.5">
							<label class="flex items-center gap-2 text-sm text-gray-300">
								<input type="checkbox" bind:checked={subnetForm.dhcp} class="rounded border-gray-600" />
								DHCP 활성화
							</label>
						</div>
					</div>
					{#if subnetError}
						<p class="text-red-400 text-xs">{subnetError}</p>
					{/if}
					<div class="flex justify-end">
						<button
							onclick={addSubnet}
							disabled={addingSubnet}
							class="text-sm px-4 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 text-white rounded transition-colors"
						>
							{addingSubnet ? '추가 중...' : '서브넷 추가'}
						</button>
					</div>
				</div>
			{/if}

			{#if network.subnet_details.length > 0}
				<div class="space-y-3">
					{#each network.subnet_details as subnet}
						{#if editingSubnetId === subnet.id}
							<div class="bg-gray-800 rounded-lg p-4 space-y-3">
								<div class="grid grid-cols-2 gap-3">
									<div>
										<label class="block text-xs text-gray-400 mb-1">이름
											<input
												bind:value={editSubnetForm.name}
												type="text"
												class="w-full bg-gray-700 border border-gray-600 rounded px-2.5 py-1.5 text-white text-sm focus:outline-none focus:border-blue-500 mt-1"
											/>
										</label>
									</div>
									<div>
										<label class="block text-xs text-gray-400 mb-1">게이트웨이
											<input
												bind:value={editSubnetForm.gateway}
												type="text"
												placeholder={subnet.gateway_ip ?? '없음'}
												class="w-full bg-gray-700 border border-gray-600 rounded px-2.5 py-1.5 text-white text-sm font-mono focus:outline-none focus:border-blue-500 mt-1"
											/>
										</label>
									</div>
									<div class="flex items-center">
										<label class="flex items-center gap-2 text-sm text-gray-300">
											<input type="checkbox" bind:checked={editSubnetForm.dhcp} class="rounded border-gray-600" />
											DHCP 활성화
										</label>
									</div>
								</div>
								{#if editSubnetError}
									<p class="text-red-400 text-xs">{editSubnetError}</p>
								{/if}
								<div class="flex justify-end gap-2">
									<button
										onclick={() => { editingSubnetId = null; }}
										class="text-xs text-gray-400 hover:text-gray-200 px-3 py-1.5 transition-colors"
									>취소</button>
									<button
										onclick={saveSubnet}
										disabled={savingSubnet}
										class="text-xs px-4 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 text-white rounded transition-colors"
									>{savingSubnet ? '저장 중...' : '저장'}</button>
								</div>
							</div>
						{:else}
							<div class="bg-gray-800/50 rounded-lg p-4">
								<div class="flex items-start justify-between mb-3">
									<div>
										<h3 class="text-sm font-medium text-white">{subnet.name || '(이름 없음)'}</h3>
										<span class="text-xs text-gray-500 font-mono">{subnet.id}</span>
									</div>
									<div class="flex items-center gap-1">
										<button
											onclick={() => startEditSubnet(subnet)}
											class="text-xs text-blue-400 hover:text-blue-300 px-2 py-1 border border-blue-900 hover:border-blue-700 rounded transition-colors"
										>편집</button>
										<button
											onclick={() => deleteSubnet(subnet.id, subnet.name)}
											disabled={deletingSubnetId === subnet.id}
											class="text-xs text-red-400 hover:text-red-300 disabled:text-gray-600 px-2 py-1 border border-red-900 hover:border-red-700 disabled:border-gray-700 rounded transition-colors"
										>{deletingSubnetId === subnet.id ? '삭제 중...' : '삭제'}</button>
									</div>
								</div>
								<dl class="grid grid-cols-2 md:grid-cols-4 gap-x-6 gap-y-2">
									<div>
										<dt class="text-xs text-gray-500 mb-0.5">CIDR</dt>
										<dd class="text-sm text-gray-300 font-mono">{subnet.cidr}</dd>
									</div>
									<div>
										<dt class="text-xs text-gray-500 mb-0.5">게이트웨이</dt>
										<dd class="text-sm text-gray-300 font-mono">{subnet.gateway_ip ?? '-'}</dd>
									</div>
									<div>
										<dt class="text-xs text-gray-500 mb-0.5">DHCP</dt>
										<dd>
											{#if subnet.dhcp_enabled}
												<span class="px-1.5 py-0.5 bg-green-900/30 text-green-400 rounded text-xs">활성</span>
											{:else}
												<span class="px-1.5 py-0.5 bg-gray-800 text-gray-500 rounded text-xs">비활성</span>
											{/if}
										</dd>
									</div>
									<div>
										<dt class="text-xs text-gray-500 mb-0.5">IP 버전</dt>
										<dd class="text-sm text-gray-300">IPv4</dd>
									</div>
								</dl>
							</div>
						{/if}
					{/each}
				</div>
			{:else}
				<p class="text-sm text-gray-500">서브넷 없음</p>
			{/if}
		</div>

		<!-- 연결된 라우터 -->
		{#if network.routers.length > 0}
			<div class="bg-gray-900 border border-gray-800 rounded-lg p-6">
				<h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-4">연결된 라우터</h2>
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
							<th class="text-left py-2 pr-6">이름</th>
							<th class="text-left py-2 pr-6">외부 게이트웨이</th>
							<th class="text-left py-2">연결된 서브넷</th>
						</tr>
					</thead>
					<tbody>
						{#each network.routers as router}
							<tr class="border-b border-gray-800/50">
								<td class="py-2 pr-6 text-gray-300">{router.name || router.id.slice(0, 12) + '...'}</td>
								<td class="py-2 pr-6">
									{#if router.external_gateway_network_id}
										<span class="text-orange-300 text-xs font-mono">{router.external_gateway_network_id.slice(0, 12)}...</span>
									{:else}
										<span class="text-gray-600 text-xs">-</span>
									{/if}
								</td>
								<td class="py-2 text-gray-500 text-xs">
									{router.connected_subnet_ids.length}개
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	{/if}
</div>
