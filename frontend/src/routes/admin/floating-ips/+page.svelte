<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api } from '$lib/api/client';

	interface FloatingIpInfo {
		id: string;
		floating_ip_address: string;
		fixed_ip_address: string | null;
		status: string;
		port_id: string | null;
		project_id: string | null;
	}

	let fips = $state<FloatingIpInfo[]>([]);
	let loading = $state(true);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function load() {
		loading = true;
		try {
			fips = await api.get<FloatingIpInfo[]>('/api/admin/all-floating-ips', token, projectId);
		} catch {
			fips = [];
		} finally {
			loading = false;
		}
	}

	onMount(load);
</script>

<div class="p-4 md:p-8 max-w-6xl">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-white">전체 Floating IP</h1>
		<button onclick={load} class="text-xs text-gray-400 hover:text-white px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600">새로고침</button>
	</div>

	{#if loading}
		<div class="text-gray-500 text-sm">로딩 중...</div>
	{:else}
		<div class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
						<th class="text-left py-2 pr-4">Floating IP</th>
						<th class="text-left py-2 pr-4">Fixed IP</th>
						<th class="text-left py-2 pr-4">상태</th>
						<th class="text-left py-2">프로젝트</th>
					</tr>
				</thead>
				<tbody>
					{#each fips as f (f.id)}
						<tr class="border-b border-gray-800/50 text-xs">
							<td class="py-2 pr-4 font-mono text-green-400">{f.floating_ip_address}</td>
							<td class="py-2 pr-4 font-mono text-gray-400">{f.fixed_ip_address ?? '-'}</td>
							<td class="py-2 pr-4 {f.port_id ? 'text-green-400' : 'text-gray-500'}">
								{f.port_id ? '할당됨' : '미할당'}
							</td>
							<td class="py-2 text-gray-500 font-mono">{f.project_id?.slice(0, 8) ?? '-'}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		<div class="mt-3 flex gap-4 text-xs text-gray-500">
			<span>총 {fips.length}개</span>
			<span class="text-green-400">할당됨: {fips.filter(f => f.port_id).length}개</span>
			<span>미할당: {fips.filter(f => !f.port_id).length}개</span>
		</div>
	{/if}
</div>
