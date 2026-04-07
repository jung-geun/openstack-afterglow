<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import { formatNumber } from '$lib/utils/format';

	interface AdminShare {
		id: string;
		name: string;
		status: string;
		size: number;
		share_proto: string;
		metadata: Record<string, string>;
	}

	const statusColor: Record<string, string> = {
		available: 'text-green-400', creating: 'text-yellow-400',
		deleting: 'text-orange-400', error: 'text-red-400',
	};

	let shares = $state<AdminShare[]>([]);
	let loading = $state(true);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function load() {
		loading = true;
		try {
			shares = await api.get<AdminShare[]>('/api/admin/all-shares', token, projectId);
		} catch {
			shares = [];
		} finally {
			loading = false;
		}
	}

	onMount(load);
</script>

<div class="p-8 max-w-6xl">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-white">전체 공유 스토리지</h1>
		<button onclick={load} class="text-xs text-gray-400 hover:text-white transition-colors px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600">새로고침</button>
	</div>

	{#if loading}
		<LoadingSkeleton variant="table" rows={5} />
	{:else if shares.length === 0}
		<div class="text-gray-600 text-sm">공유 스토리지가 없습니다</div>
	{:else}
		<div class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
						<th class="text-left py-2 pr-4">이름</th>
						<th class="text-left py-2 pr-4">상태</th>
						<th class="text-left py-2 pr-4">크기</th>
						<th class="text-left py-2 pr-4">프로토콜</th>
						<th class="text-left py-2">유형</th>
					</tr>
				</thead>
				<tbody>
					{#each shares as s (s.id)}
						<tr class="border-b border-gray-800/50 text-xs">
							<td class="py-2 pr-4 text-white">{s.name || s.id.slice(0, 8)}</td>
							<td class="py-2 pr-4 {statusColor[s.status] ?? 'text-gray-400'}">{s.status}</td>
							<td class="py-2 pr-4 text-gray-400">{formatNumber(s.size)} GB</td>
							<td class="py-2 pr-4 text-gray-400">{s.share_proto}</td>
							<td class="py-2 text-gray-500">{s.metadata?.union_type || '-'}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>
