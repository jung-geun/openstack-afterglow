<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api } from '$lib/api/client';

	interface PortInfo {
		id: string;
		name: string;
		status: string;
		network_id: string;
		device_owner: string;
		device_id: string;
		mac_address: string;
		fixed_ips: { ip_address: string; subnet_id: string }[];
		project_id: string | null;
	}

	let ports = $state<PortInfo[]>([]);
	let loading = $state(true);
	let filter = $state('');

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	const filtered = $derived(
		filter
			? ports.filter(p =>
				p.name?.includes(filter) ||
				p.device_owner?.includes(filter) ||
				p.fixed_ips.some(ip => ip.ip_address?.includes(filter)) ||
				p.project_id?.includes(filter)
			)
			: ports
	);

	async function load() {
		loading = true;
		try {
			ports = await api.get<PortInfo[]>('/api/admin/all-ports', token, projectId);
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
		<h1 class="text-2xl font-bold text-white">전체 포트</h1>
		<div class="flex items-center gap-3">
			<input
				type="text"
				bind:value={filter}
				placeholder="필터 (이름, device_owner, IP, 프로젝트)"
				class="text-xs bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-gray-300 placeholder-gray-600 w-64"
			/>
			<button onclick={load} class="text-xs text-gray-400 hover:text-white px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600">새로고침</button>
		</div>
	</div>

	{#if loading}
		<div class="text-gray-500 text-sm">로딩 중...</div>
	{:else}
		<div class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
						<th class="text-left py-2 pr-4">이름/ID</th>
						<th class="text-left py-2 pr-4">상태</th>
						<th class="text-left py-2 pr-4">Device Owner</th>
						<th class="text-left py-2 pr-4">IP 주소</th>
						<th class="text-left py-2">프로젝트</th>
					</tr>
				</thead>
				<tbody>
					{#each filtered as p (p.id)}
						<tr class="border-b border-gray-800/50 text-xs">
							<td class="py-2 pr-4">
								<div class="text-white">{p.name || '-'}</div>
								<div class="text-gray-600 font-mono">{p.id.slice(0, 12)}...</div>
							</td>
							<td class="py-2 pr-4 {p.status === 'ACTIVE' ? 'text-green-400' : 'text-gray-400'}">{p.status}</td>
							<td class="py-2 pr-4 text-gray-500 text-xs break-all max-w-[160px]">{p.device_owner || '-'}</td>
							<td class="py-2 pr-4 font-mono text-gray-400">
								{#each p.fixed_ips as ip}
									<div>{ip.ip_address}</div>
								{/each}
								{#if p.fixed_ips.length === 0}-{/if}
							</td>
							<td class="py-2 text-gray-500 font-mono">{p.project_id?.slice(0, 8) ?? '-'}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		<div class="mt-3 text-xs text-gray-600">
			{filtered.length}/{ports.length}개 포트
		</div>
	{/if}
</div>
