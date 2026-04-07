<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';

	interface AdminContainer {
		uuid: string;
		name: string;
		status: string;
		image: string | null;
		cpu: number | null;
		memory: string | null;
		created_at: string | null;
	}

	const statusColor: Record<string, string> = {
		Running: 'text-green-400', Stopped: 'text-gray-400', ERROR: 'text-red-400',
	};

	let containers = $state<AdminContainer[]>([]);
	let loading = $state(true);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function load() {
		loading = true;
		try {
			containers = await api.get<AdminContainer[]>('/api/admin/all-containers', token, projectId);
		} catch {
			containers = [];
		} finally {
			loading = false;
		}
	}

	onMount(load);
</script>

<div class="p-8 max-w-6xl">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-white">전체 컨테이너</h1>
		<button onclick={load} class="text-xs text-gray-400 hover:text-white transition-colors px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600">새로고침</button>
	</div>

	{#if loading}
		<LoadingSkeleton variant="table" rows={5} />
	{:else if containers.length === 0}
		<div class="text-gray-600 text-sm">컨테이너가 없습니다</div>
	{:else}
		<div class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
						<th class="text-left py-2 pr-4">이름</th>
						<th class="text-left py-2 pr-4">상태</th>
						<th class="text-left py-2 pr-4">이미지</th>
						<th class="text-left py-2 pr-4">CPU</th>
						<th class="text-left py-2 pr-4">메모리</th>
						<th class="text-left py-2">생성일</th>
					</tr>
				</thead>
				<tbody>
					{#each containers as c (c.uuid)}
						<tr class="border-b border-gray-800/50 text-xs">
							<td class="py-2 pr-4 text-white">{c.name || c.uuid.slice(0, 8)}</td>
							<td class="py-2 pr-4 {statusColor[c.status] ?? 'text-gray-400'}">{c.status}</td>
							<td class="py-2 pr-4 text-gray-400 font-mono text-xs">{c.image || '-'}</td>
							<td class="py-2 pr-4 text-gray-400">{c.cpu ?? '-'}</td>
							<td class="py-2 pr-4 text-gray-400">{c.memory || '-'}</td>
							<td class="py-2 text-gray-500">{c.created_at?.slice(0, 10) ?? '-'}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>
