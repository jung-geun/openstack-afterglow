<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import { formatStorage } from '$lib/utils/format';

	interface SwiftContainer {
		name: string;
		count: number;
		bytes: number;
	}

	interface AccountMeta {
		container_count: number;
		object_count: number;
		bytes_used: number;
	}

	let containers = $state<SwiftContainer[]>([]);
	let account = $state<AccountMeta | null>(null);
	let loading = $state(true);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function load() {
		loading = true;
		try {
			[containers, account] = await Promise.all([
				api.get<SwiftContainer[]>('/api/object-storage', token, projectId),
				api.get<AccountMeta>('/api/object-storage/account', token, projectId),
			]);
		} catch {
			containers = [];
		} finally {
			loading = false;
		}
	}

	onMount(load);
</script>

<div class="p-4 md:p-8 max-w-6xl">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-white">Object Storage</h1>
		<button onclick={load} class="text-xs text-gray-400 hover:text-white transition-colors px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600">새로고침</button>
	</div>

	{#if account}
		<div class="grid grid-cols-3 gap-4 mb-6">
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
				<div class="text-xs text-gray-500 uppercase tracking-wide mb-1">컨테이너</div>
				<div class="text-2xl font-bold text-white">{account.container_count}</div>
			</div>
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
				<div class="text-xs text-gray-500 uppercase tracking-wide mb-1">오브젝트</div>
				<div class="text-2xl font-bold text-white">{account.object_count}</div>
			</div>
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
				<div class="text-xs text-gray-500 uppercase tracking-wide mb-1">사용 용량</div>
				<div class="text-2xl font-bold text-white">{formatStorage(Math.round(account.bytes_used / 1073741824))}</div>
			</div>
		</div>
	{/if}

	{#if loading}
		<LoadingSkeleton variant="table" rows={5} />
	{:else if containers.length === 0}
		<div class="text-gray-600 text-sm">컨테이너가 없습니다</div>
	{:else}
		<div class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
						<th class="text-left py-3 px-4 font-medium">컨테이너 이름</th>
						<th class="text-left py-3 px-4 font-medium">오브젝트 수</th>
						<th class="text-left py-3 px-4 font-medium">용량</th>
					</tr>
				</thead>
				<tbody>
					{#each containers as c}
						<tr class="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
							<td class="py-3 px-4 text-white font-medium">{c.name}</td>
							<td class="py-3 px-4 text-gray-300">{c.count}</td>
							<td class="py-3 px-4 text-gray-300">{formatStorage(Math.round(c.bytes / 1073741824))}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>
