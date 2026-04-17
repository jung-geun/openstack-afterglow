<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';

	interface Port {
		id: string;
		name: string;
		status: string;
		mac_address: string;
		fixed_ips: { ip_address: string; subnet_id: string }[];
		network_id: string;
		device_owner: string;
		device_id: string;
	}

	const statusColor: Record<string, string> = {
		ACTIVE: 'text-green-400',
		DOWN: 'text-gray-500',
		BUILD: 'text-yellow-400',
		ERROR: 'text-red-400',
	};

	let ports = $state<Port[]>([]);
	let loading = $state(true);
	let searchText = $state('');

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	const filteredPorts = $derived(
		searchText
			? ports.filter(
					(p) =>
						(p.name || p.id).toLowerCase().includes(searchText.toLowerCase()) ||
						p.device_owner.toLowerCase().includes(searchText.toLowerCase()) ||
						p.fixed_ips.some((ip) => ip.ip_address.includes(searchText))
				)
			: ports
	);

	// device_owner를 읽기 쉬운 레이블로 변환
	function ownerLabel(owner: string): string {
		if (!owner) return '-';
		if (owner === 'compute:nova') return 'VM';
		if (owner === 'network:router_interface') return '라우터';
		if (owner === 'network:router_gateway') return '게이트웨이';
		if (owner === 'network:dhcp') return 'DHCP';
		if (owner === 'network:floatingip') return 'Floating IP';
		if (owner === 'network:ha_router_replicated_interface') return 'HA 라우터';
		if (owner.startsWith('compute:')) return 'VM';
		if (owner.startsWith('network:')) return owner.replace('network:', '');
		return owner;
	}

	async function load() {
		loading = true;
		try {
			ports = await api.get<Port[]>('/api/networks/ports', token, projectId);
		} catch {
			ports = [];
		} finally {
			loading = false;
		}
	}

	onMount(load);
</script>

<div class="p-4 md:p-8 max-w-6xl">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-white">포트</h1>
		<button
			onclick={load}
			class="text-xs text-gray-400 hover:text-white transition-colors px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600"
		>
			새로고침
		</button>
	</div>

	{#if !loading}
		<div class="mb-4">
			<input
				type="text"
				bind:value={searchText}
				placeholder="이름, IP, 소유자 검색..."
				class="w-full max-w-xs bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-gray-500"
			/>
		</div>
	{/if}

	{#if loading}
		<LoadingSkeleton variant="table" rows={8} />
	{:else if filteredPorts.length === 0}
		<div class="text-gray-600 text-sm">{searchText ? '검색 결과가 없습니다' : '포트가 없습니다'}</div>
	{:else}
		<div class="text-xs text-gray-500 mb-2">{filteredPorts.length}개</div>
		<div class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
						<th class="text-left py-2 pr-4">이름 / ID</th>
						<th class="text-left py-2 pr-4">상태</th>
						<th class="text-left py-2 pr-4">MAC</th>
						<th class="text-left py-2 pr-4">Fixed IP</th>
						<th class="text-left py-2 pr-4">소유자</th>
					</tr>
				</thead>
				<tbody>
					{#each filteredPorts as p (p.id)}
						<tr class="border-b border-gray-800/50 text-xs hover:bg-gray-800/20 transition-colors">
							<td class="py-2.5 pr-4">
								<div class="text-gray-300">{p.name || '-'}</div>
								<div class="text-gray-600 font-mono text-xs">{p.id.slice(0, 12)}...</div>
							</td>
							<td class="py-2.5 pr-4 {statusColor[p.status] ?? 'text-gray-400'}">{p.status}</td>
							<td class="py-2.5 pr-4 text-gray-400 font-mono text-xs">{p.mac_address}</td>
							<td class="py-2.5 pr-4">
								{#if p.fixed_ips.length > 0}
									{#each p.fixed_ips as fip}
										<div class="text-gray-300 font-mono text-xs">{fip.ip_address}</div>
									{/each}
								{:else}
									<span class="text-gray-600">-</span>
								{/if}
							</td>
							<td class="py-2.5 pr-4 text-gray-400 text-xs">{ownerLabel(p.device_owner)}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>
