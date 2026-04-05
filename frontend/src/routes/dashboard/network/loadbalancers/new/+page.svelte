<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import { goto } from '$app/navigation';

	interface Network {
		id: string;
		name: string;
		subnets: string[];
		is_external: boolean;
	}

	interface SubnetDetail {
		id: string;
		name: string;
		cidr: string;
	}

	let networks = $state<Network[]>([]);
	let subnets = $state<SubnetDetail[]>([]);
	let form = $state({ name: '', vip_subnet_id: '', vip_network_id: '', description: '' });
	let creating = $state(false);
	let error = $state('');
	let loadingSubnets = $state(false);

	async function loadNetworks() {
		try {
			networks = await api.get<Network[]>('/api/networks', $auth.token ?? undefined, $auth.projectId ?? undefined);
		} catch {
			// ignore
		}
	}

	async function onNetworkChange() {
		form.vip_subnet_id = '';
		subnets = [];
		if (!form.vip_network_id) return;
		loadingSubnets = true;
		try {
			const detail = await api.get<{ subnet_details: SubnetDetail[] }>(
				`/api/networks/${form.vip_network_id}`,
				$auth.token ?? undefined, $auth.projectId ?? undefined
			);
			subnets = detail.subnet_details ?? [];
		} catch {
			subnets = [];
		} finally {
			loadingSubnets = false;
		}
	}

	async function createLb() {
		if (!form.name.trim() || !form.vip_subnet_id) {
			error = '이름과 VIP 서브넷을 입력해주세요';
			return;
		}
		creating = true;
		error = '';
		try {
			const lb = await api.post<{ id: string }>(
				'/api/loadbalancers',
				{ name: form.name, vip_subnet_id: form.vip_subnet_id, description: form.description },
				$auth.token ?? undefined, $auth.projectId ?? undefined
			);
			goto(`/dashboard/network/loadbalancers/${lb.id}`);
		} catch (e) {
			error = e instanceof ApiError ? e.message : '생성 실패';
		} finally {
			creating = false;
		}
	}

	$effect(() => {
		if ($auth.token) loadNetworks();
	});
</script>

<div class="p-8 max-w-lg">
	<div class="flex items-center gap-4 mb-8">
		<button onclick={() => goto('/dashboard/network/loadbalancers')} class="text-gray-500 hover:text-white transition-colors text-sm">
			← 로드밸런서 목록
		</button>
		<h1 class="text-2xl font-bold text-white">로드밸런서 생성</h1>
	</div>

	<div class="bg-gray-900 border border-gray-700 rounded-xl p-6 space-y-5">
		{#if error}
			<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">{error}</div>
		{/if}

		<div>
			<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름</label>
			<input
				bind:value={form.name}
				type="text"
				placeholder="my-lb"
				class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500"
			/>
		</div>

		<div>
			<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">네트워크</label>
			<select
				bind:value={form.vip_network_id}
				onchange={onNetworkChange}
				class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500"
			>
				<option value="">네트워크 선택</option>
				{#each networks.filter(n => !n.is_external) as net}
					<option value={net.id}>{net.name}</option>
				{/each}
			</select>
		</div>

		{#if form.vip_network_id}
			<div>
				<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">VIP 서브넷</label>
				{#if loadingSubnets}
					<div class="text-gray-500 text-sm">서브넷 로딩 중...</div>
				{:else if subnets.length === 0}
					<div class="text-gray-500 text-sm">서브넷이 없습니다</div>
				{:else}
					<select
						bind:value={form.vip_subnet_id}
						class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500"
					>
						<option value="">서브넷 선택</option>
						{#each subnets as subnet}
							<option value={subnet.id}>{subnet.name || subnet.id.slice(0, 8)} ({subnet.cidr})</option>
						{/each}
					</select>
				{/if}
			</div>
		{/if}

		<div>
			<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">설명 (선택)</label>
			<input
				bind:value={form.description}
				type="text"
				placeholder="설명"
				class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500"
			/>
		</div>

		<div class="flex justify-end gap-3 pt-2">
			<button
				onclick={() => goto('/dashboard/network/loadbalancers')}
				class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors"
			>
				취소
			</button>
			<button
				onclick={createLb}
				disabled={creating}
				class="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors"
			>
				{creating ? '생성 중...' : '생성'}
			</button>
		</div>
	</div>
</div>
