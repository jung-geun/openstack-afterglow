<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api } from '$lib/api/client';

	interface RouterInfo {
		id: string;
		name: string;
		status: string;
		external_gateway_network_id: string | null;
		connected_subnet_ids: string[];
		project_id: string | null;
	}

	let routers = $state<RouterInfo[]>([]);
	let loading = $state(true);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function load() {
		loading = true;
		try {
			routers = await api.get<RouterInfo[]>('/api/admin/all-routers', token, projectId);
		} catch {
			routers = [];
		} finally {
			loading = false;
		}
	}

	onMount(load);
</script>

<div class="p-4 md:p-8 max-w-6xl">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-white">전체 라우터</h1>
		<button onclick={load} class="text-xs text-gray-400 hover:text-white px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600">새로고침</button>
	</div>

	{#if loading}
		<div class="text-gray-500 text-sm">로딩 중...</div>
	{:else}
		<div class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
						<th class="text-left py-2 pr-4">이름</th>
						<th class="text-left py-2 pr-4">상태</th>
						<th class="text-left py-2 pr-4">외부 게이트웨이</th>
						<th class="text-left py-2 pr-4">연결 서브넷</th>
						<th class="text-left py-2">프로젝트</th>
					</tr>
				</thead>
				<tbody>
					{#each routers as r (r.id)}
						<tr class="border-b border-gray-800/50 text-xs">
							<td class="py-2 pr-4 text-white">{r.name || r.id.slice(0, 8)}</td>
							<td class="py-2 pr-4 {r.status === 'ACTIVE' ? 'text-green-400' : 'text-gray-400'}">{r.status}</td>
							<td class="py-2 pr-4 text-gray-500 font-mono">
								{r.external_gateway_network_id ? r.external_gateway_network_id.slice(0, 8) + '...' : '-'}
							</td>
							<td class="py-2 pr-4 text-gray-500">{r.connected_subnet_ids.length}개</td>
							<td class="py-2 text-gray-500 font-mono">{r.project_id?.slice(0, 8) ?? '-'}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		<div class="mt-3 text-xs text-gray-600">총 {routers.length}개 라우터</div>
	{/if}
</div>
