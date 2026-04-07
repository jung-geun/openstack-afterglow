<script lang="ts">
	import { page } from '$app/stores';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import { goto } from '$app/navigation';

	interface Listener {
		id: string;
		name: string;
		protocol: string;
		protocol_port: number;
		status: string;
		default_pool_id: string | null;
	}

	interface Pool {
		id: string;
		name: string;
		protocol: string;
		lb_algorithm: string;
		status: string;
	}

	interface Member {
		id: string;
		name: string;
		address: string;
		protocol_port: number;
		weight: number;
		status: string;
	}

	interface LoadBalancerDetail {
		id: string;
		name: string;
		description: string;
		status: string;
		operating_status: string;
		vip_address: string | null;
		vip_subnet_id: string | null;
	}

	const id = $derived($page.params.id);

	let lb = $state<LoadBalancerDetail | null>(null);
	let listeners = $state<Listener[]>([]);
	let pools = $state<Pool[]>([]);
	let selectedPoolMembers = $state<Member[]>([]);
	let selectedPoolId = $state<string | null>(null);
	let loading = $state(true);
	let error = $state('');
	let saving = $state(false);

	interface LbStatusNode {
		id: string;
		name: string;
		provisioning_status: string;
		operating_status: string;
		listeners?: LbStatusNode[];
		pools?: LbStatusNode[];
		members?: LbStatusNode[];
	}
	let statusTree = $state<LbStatusNode | null>(null);

	// 리스너 생성
	let showAddListener = $state(false);
	let listenerForm = $state({ protocol: 'HTTP', protocol_port: 80, name: '' });

	// 풀 생성
	let showAddPool = $state(false);
	let poolForm = $state({ protocol: 'HTTP', lb_algorithm: 'ROUND_ROBIN', name: '' });

	// 멤버 추가
	let showAddMember = $state(false);
	let memberForm = $state({ address: '', protocol_port: 80, weight: 1, name: '' });

	async function fetchAll() {
		loading = true;
		try {
			const [lbData, listenersData, poolsData] = await Promise.all([
				api.get<LoadBalancerDetail>(`/api/loadbalancers/${id}`, $auth.token ?? undefined, $auth.projectId ?? undefined),
				api.get<Listener[]>(`/api/loadbalancers/${id}/listeners`, $auth.token ?? undefined, $auth.projectId ?? undefined),
				api.get<Pool[]>(`/api/loadbalancers/${id}/pools`, $auth.token ?? undefined, $auth.projectId ?? undefined),
			]);
			lb = lbData;
			listeners = listenersData;
			pools = poolsData;
			error = '';
			if (lbData.status === 'ERROR') {
				api.get<LbStatusNode>(`/api/loadbalancers/${id}/status`, $auth.token ?? undefined, $auth.projectId ?? undefined)
					.then(tree => { statusTree = tree; })
					.catch(() => {});
			}
		} catch (e) {
			error = e instanceof ApiError ? e.message : '조회 실패';
		} finally {
			loading = false;
		}
	}

	$effect(() => { if ($auth.projectId) fetchAll(); });

	$effect(() => {
		if (!selectedPoolId) { selectedPoolMembers = []; return; }
		api.get<Member[]>(`/api/loadbalancers/${id}/pools/${selectedPoolId}/members`, $auth.token ?? undefined, $auth.projectId ?? undefined)
			.then(m => { selectedPoolMembers = m; })
			.catch(() => {});
	});

	async function createListener() {
		saving = true;
		try {
			await api.post(`/api/loadbalancers/${id}/listeners`, listenerForm, $auth.token ?? undefined, $auth.projectId ?? undefined);
			showAddListener = false;
			listenerForm = { protocol: 'HTTP', protocol_port: 80, name: '' };
			await fetchAll();
		} catch (e) {
			alert('리스너 생성 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			saving = false;
		}
	}

	async function deleteListener(listenerId: string) {
		if (!confirm('리스너를 삭제하시겠습니까?')) return;
		saving = true;
		try {
			await api.delete(`/api/loadbalancers/${id}/listeners/${listenerId}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
			await fetchAll();
		} catch (e) {
			alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			saving = false;
		}
	}

	async function createPool() {
		saving = true;
		try {
			await api.post(`/api/loadbalancers/${id}/pools`, poolForm, $auth.token ?? undefined, $auth.projectId ?? undefined);
			showAddPool = false;
			poolForm = { protocol: 'HTTP', lb_algorithm: 'ROUND_ROBIN', name: '' };
			await fetchAll();
		} catch (e) {
			alert('풀 생성 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			saving = false;
		}
	}

	async function deletePool(poolId: string) {
		if (!confirm('풀을 삭제하시겠습니까?')) return;
		saving = true;
		try {
			await api.delete(`/api/loadbalancers/${id}/pools/${poolId}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
			if (selectedPoolId === poolId) selectedPoolId = null;
			await fetchAll();
		} catch (e) {
			alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			saving = false;
		}
	}

	async function addMember() {
		if (!selectedPoolId) return;
		saving = true;
		try {
			await api.post(`/api/loadbalancers/${id}/pools/${selectedPoolId}/members`, memberForm, $auth.token ?? undefined, $auth.projectId ?? undefined);
			showAddMember = false;
			memberForm = { address: '', protocol_port: 80, weight: 1, name: '' };
			selectedPoolMembers = await api.get<Member[]>(`/api/loadbalancers/${id}/pools/${selectedPoolId}/members`, $auth.token ?? undefined, $auth.projectId ?? undefined);
		} catch (e) {
			alert('멤버 추가 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			saving = false;
		}
	}

	async function removeMember(memberId: string) {
		if (!selectedPoolId || !confirm('멤버를 제거하시겠습니까?')) return;
		saving = true;
		try {
			await api.delete(`/api/loadbalancers/${id}/pools/${selectedPoolId}/members/${memberId}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
			selectedPoolMembers = selectedPoolMembers.filter(m => m.id !== memberId);
		} catch (e) {
			alert('제거 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			saving = false;
		}
	}

	async function deleteLb() {
		if (!confirm(`로드밸런서 "${lb?.name || id}"을 삭제하시겠습니까? (연결된 리스너/풀/멤버도 모두 삭제됩니다)`)) return;
		saving = true;
		try {
			await api.delete(`/api/loadbalancers/${id}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
			goto('/dashboard/network/loadbalancers');
		} catch (e) {
			alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
			saving = false;
		}
	}
</script>

<div class="max-w-4xl mx-auto px-4 py-8 text-gray-100">
	<button onclick={() => goto('/dashboard/network/loadbalancers')} class="text-sm text-gray-400 hover:text-gray-200 mb-6 inline-flex items-center gap-1">
		← 로드밸런서 목록
	</button>

	{#if loading}
		<div class="text-gray-500">불러오는 중...</div>
	{:else if error}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">{error}</div>
	{:else if lb}
		<!-- 헤더 -->
		<div class="flex items-start justify-between mb-8">
			<div>
				<h1 class="text-2xl font-bold text-white">{lb.name || lb.id.slice(0, 12)}</h1>
				{#if lb.description}
					<p class="text-gray-400 text-sm mt-1">{lb.description}</p>
				{/if}
				<div class="flex items-center gap-3 mt-2">
					<span class="px-2 py-0.5 rounded text-xs {lb.status === 'ACTIVE' ? 'text-green-400 bg-green-900/30' : 'text-yellow-400 bg-yellow-900/30'}">{lb.status}</span>
					<span class="px-2 py-0.5 rounded text-xs {lb.operating_status === 'ONLINE' ? 'text-green-400' : 'text-gray-400'}">{lb.operating_status}</span>
					{#if lb.vip_address}
						<span class="text-xs text-gray-500 font-mono">VIP: {lb.vip_address}</span>
					{/if}
				</div>
			</div>
			<button onclick={deleteLb} disabled={saving} class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors">삭제</button>
		</div>

		<!-- 에러 상태 상세 -->
		{#if lb.status === 'ERROR' || lb.status?.includes('ERROR')}
			<div class="bg-red-900/20 border border-red-800 rounded-lg p-5 mb-4">
				<h2 class="text-sm font-semibold text-red-400 mb-3 flex items-center gap-2">
					<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>
					오류 상세 정보
				</h2>
				{#if statusTree}
					<div class="space-y-2 text-xs font-mono">
						<div class="flex items-center gap-3">
							<span class="text-gray-400 w-32 shrink-0">LB 상태</span>
							<span class="text-red-400">{statusTree.provisioning_status ?? lb.status}</span>
							<span class="text-gray-500">{statusTree.operating_status ?? lb.operating_status}</span>
						</div>
						{#if statusTree.listeners && statusTree.listeners.length > 0}
							{#each statusTree.listeners as listener}
								<div class="ml-4 flex items-center gap-3">
									<span class="text-gray-500 w-28 shrink-0">└ 리스너</span>
									<span class="text-gray-300">{listener.name || listener.id?.slice(0, 12)}</span>
									<span class="{listener.provisioning_status === 'ERROR' ? 'text-red-400' : 'text-gray-400'}">{listener.provisioning_status}</span>
								</div>
								{#if listener.pools}
									{#each listener.pools as pool}
										<div class="ml-8 flex items-center gap-3">
											<span class="text-gray-500 w-24 shrink-0">└ 풀</span>
											<span class="text-gray-300">{pool.name || pool.id?.slice(0, 12)}</span>
											<span class="{pool.provisioning_status === 'ERROR' ? 'text-red-400' : 'text-gray-400'}">{pool.provisioning_status}</span>
										</div>
										{#if pool.members}
											{#each pool.members as member}
												<div class="ml-12 flex items-center gap-3">
													<span class="text-gray-500 w-20 shrink-0">└ 멤버</span>
													<span class="text-gray-300">{member.name || member.id?.slice(0, 12)}</span>
													<span class="{member.provisioning_status === 'ERROR' ? 'text-red-400' : 'text-gray-400'}">{member.provisioning_status}</span>
												</div>
											{/each}
										{/if}
									{/each}
								{/if}
							{/each}
						{/if}
						{#if statusTree.pools && statusTree.pools.length > 0 && (!statusTree.listeners || statusTree.listeners.length === 0)}
							{#each statusTree.pools as pool}
								<div class="ml-4 flex items-center gap-3">
									<span class="text-gray-500 w-28 shrink-0">└ 풀</span>
									<span class="text-gray-300">{pool.name || pool.id?.slice(0, 12)}</span>
									<span class="{pool.provisioning_status === 'ERROR' ? 'text-red-400' : 'text-gray-400'}">{pool.provisioning_status}</span>
								</div>
							{/each}
						{/if}
					</div>
				{:else}
					<p class="text-xs text-red-300">상태 트리를 불러오는 중이거나 조회할 수 없습니다.</p>
				{/if}
			</div>
		{/if}

		<!-- 리스너 -->
		<section class="bg-gray-900 border border-gray-800 rounded-lg p-5 mb-4">
			<div class="flex items-center justify-between mb-4">
				<h2 class="font-semibold text-white">리스너 ({listeners.length})</h2>
				<button onclick={() => showAddListener = !showAddListener} class="text-blue-400 hover:text-blue-300 text-xs px-2 py-1 rounded border border-blue-900 hover:border-blue-700 transition-colors">+ 추가</button>
			</div>

			{#if showAddListener}
				<div class="mb-4 p-4 bg-gray-800/60 border border-gray-700 rounded-lg grid grid-cols-1 sm:grid-cols-3 gap-2">
					<input bind:value={listenerForm.name} placeholder="이름 (선택)" class="bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200" />
					<select bind:value={listenerForm.protocol} class="bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200">
						{#each ['HTTP', 'HTTPS', 'TCP', 'UDP'] as p}
							<option value={p}>{p}</option>
						{/each}
					</select>
					<input bind:value={listenerForm.protocol_port} type="number" min="1" max="65535" placeholder="포트" class="bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200" />
					<button onclick={createListener} disabled={saving} class="col-span-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 text-white text-sm px-3 py-2 rounded">생성</button>
					<button onclick={() => showAddListener = false} class="text-gray-400 hover:text-gray-200 text-sm px-2 text-center">취소</button>
				</div>
			{/if}

			{#if listeners.length === 0}
				<p class="text-sm text-gray-600">리스너가 없습니다.</p>
			{:else}
				<div class="space-y-2">
					{#each listeners as l}
						<div class="flex items-center justify-between bg-gray-800/50 rounded-lg px-4 py-3">
							<div class="text-sm">
								<span class="text-white font-medium">{l.name || l.id.slice(0, 10)}</span>
								<span class="ml-2 text-xs text-blue-300 bg-blue-900/30 px-1.5 py-0.5 rounded">{l.protocol}:{l.protocol_port}</span>
								<span class="ml-2 text-xs {l.status === 'ACTIVE' ? 'text-green-400' : 'text-yellow-400'}">{l.status}</span>
							</div>
							<button onclick={() => deleteListener(l.id)} disabled={saving} class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-1 rounded border border-red-900 hover:border-red-700 transition-colors">삭제</button>
						</div>
					{/each}
				</div>
			{/if}
		</section>

		<!-- 풀 -->
		<section class="bg-gray-900 border border-gray-800 rounded-lg p-5 mb-4">
			<div class="flex items-center justify-between mb-4">
				<h2 class="font-semibold text-white">풀 ({pools.length})</h2>
				<button onclick={() => showAddPool = !showAddPool} class="text-blue-400 hover:text-blue-300 text-xs px-2 py-1 rounded border border-blue-900 hover:border-blue-700 transition-colors">+ 추가</button>
			</div>

			{#if showAddPool}
				<div class="mb-4 p-4 bg-gray-800/60 border border-gray-700 rounded-lg grid grid-cols-1 sm:grid-cols-3 gap-2">
					<input bind:value={poolForm.name} placeholder="이름 (선택)" class="bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200" />
					<select bind:value={poolForm.protocol} class="bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200">
						{#each ['HTTP', 'HTTPS', 'TCP', 'UDP'] as p}
							<option value={p}>{p}</option>
						{/each}
					</select>
					<select bind:value={poolForm.lb_algorithm} class="bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200">
						{#each ['ROUND_ROBIN', 'LEAST_CONNECTIONS', 'SOURCE_IP'] as a}
							<option value={a}>{a}</option>
						{/each}
					</select>
					<button onclick={createPool} disabled={saving} class="col-span-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 text-white text-sm px-3 py-2 rounded">생성</button>
					<button onclick={() => showAddPool = false} class="text-gray-400 hover:text-gray-200 text-sm px-2 text-center">취소</button>
				</div>
			{/if}

			{#if pools.length === 0}
				<p class="text-sm text-gray-600">풀이 없습니다.</p>
			{:else}
				<div class="space-y-2">
					{#each pools as pool}
						<div>
							<div
								onclick={() => selectedPoolId = selectedPoolId === pool.id ? null : pool.id}
								onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && (selectedPoolId = selectedPoolId === pool.id ? null : pool.id)}
								role="button"
								tabindex="0"
								class="flex items-center justify-between bg-gray-800/50 hover:bg-gray-800 rounded-lg px-4 py-3 cursor-pointer transition-colors {selectedPoolId === pool.id ? 'border border-blue-800' : ''}"
							>
								<div class="text-sm">
									<span class="text-white font-medium">{pool.name || pool.id.slice(0, 10)}</span>
									<span class="ml-2 text-xs text-purple-300 bg-purple-900/30 px-1.5 py-0.5 rounded">{pool.protocol}</span>
									<span class="ml-2 text-xs text-gray-500">{pool.lb_algorithm}</span>
									<span class="ml-2 text-xs {pool.status === 'ACTIVE' ? 'text-green-400' : 'text-yellow-400'}">{pool.status}</span>
								</div>
								<div class="flex gap-2">
									<span class="text-xs text-gray-500">{selectedPoolId === pool.id ? '▲ 멤버 접기' : '▼ 멤버 보기'}</span>
									<button onclick={(e) => { e.stopPropagation(); deletePool(pool.id); }} disabled={saving} class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-1 rounded border border-red-900 hover:border-red-700 transition-colors">삭제</button>
								</div>
							</div>

							{#if selectedPoolId === pool.id}
								<div class="mt-2 ml-4 bg-gray-800/30 rounded-lg p-4 border border-gray-700">
									<div class="flex items-center justify-between mb-3">
										<span class="text-sm text-gray-400">멤버 ({selectedPoolMembers.length})</span>
										<button onclick={() => showAddMember = !showAddMember} class="text-blue-400 hover:text-blue-300 text-xs px-2 py-1 rounded border border-blue-900 hover:border-blue-700 transition-colors">+ 멤버 추가</button>
									</div>

									{#if showAddMember}
										<div class="mb-3 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-2">
											<input bind:value={memberForm.address} placeholder="IP 주소" class="bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 col-span-2" />
											<input bind:value={memberForm.protocol_port} type="number" min="1" max="65535" placeholder="포트" class="bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200" />
											<input bind:value={memberForm.weight} type="number" min="1" max="256" placeholder="가중치" class="bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200" />
											<button onclick={addMember} disabled={saving || !memberForm.address} class="col-span-3 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 text-white text-sm px-3 py-2 rounded">추가</button>
											<button onclick={() => showAddMember = false} class="text-gray-400 hover:text-gray-200 text-sm px-2 text-center rounded border border-gray-700">취소</button>
										</div>
									{/if}

									{#if selectedPoolMembers.length === 0}
										<p class="text-xs text-gray-600">멤버가 없습니다.</p>
									{:else}
										<div class="space-y-1.5">
											{#each selectedPoolMembers as member}
												<div class="flex items-center justify-between bg-gray-800/50 rounded px-3 py-2">
													<div class="text-xs">
														<span class="text-white font-mono">{member.address}:{member.protocol_port}</span>
														<span class="ml-2 text-gray-500">가중치 {member.weight}</span>
														<span class="ml-2 {member.status === 'ACTIVE' ? 'text-green-400' : 'text-yellow-400'}">{member.status}</span>
													</div>
													<button onclick={() => removeMember(member.id)} disabled={saving} class="text-red-400 hover:text-red-300 text-xs">제거</button>
												</div>
											{/each}
										</div>
									{/if}
								</div>
							{/if}
						</div>
					{/each}
				</div>
			{/if}
		</section>
	{/if}
</div>
