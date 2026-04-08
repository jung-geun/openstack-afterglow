<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';

	interface ComputeService {
		id: string;
		binary: string;
		host: string;
		status: string;
		state: string;
		zone: string;
		updated_at: string | null;
		disabled_reason: string | null;
	}
	interface NetworkAgent {
		id: string;
		binary: string;
		host: string;
		agent_type: string;
		alive: boolean | null;
		admin_state_up: boolean;
		updated_at: string | null;
	}

	let computeServices = $state<ComputeService[]>([]);
	let blockStorageServices = $state<ComputeService[]>([]);
	let networkAgents = $state<NetworkAgent[]>([]);
	let loading = $state(true);
	let autoRefresh = $state(true);
	let refreshInterval = $state(30);
	let lastRefresh = $state<Date | null>(null);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function load() {
		try {
			const res = await api.get<{
				compute: ComputeService[];
				block_storage: ComputeService[];
				network: NetworkAgent[];
			}>('/api/admin/services', token, projectId);
			computeServices = res.compute || [];
			blockStorageServices = res.block_storage || [];
			networkAgents = res.network || [];
			lastRefresh = new Date();
		} catch {
			computeServices = [];
			blockStorageServices = [];
			networkAgents = [];
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		load();
	});

	$effect(() => {
		if (!autoRefresh) return;
		const interval = setInterval(load, refreshInterval * 1000);
		return () => clearInterval(interval);
	});
</script>

<div class="p-4 md:p-8 max-w-6xl">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-white">서비스 상태</h1>
		<div class="flex items-center gap-3">
			{#if lastRefresh}
				<span class="text-xs text-gray-500">마지막: {lastRefresh.toLocaleTimeString()}</span>
			{/if}
			<button
				onclick={() => { autoRefresh = !autoRefresh; }}
				class="text-xs px-3 py-1.5 rounded border transition-colors {autoRefresh ? 'border-blue-500 bg-blue-900/20 text-blue-400' : 'border-gray-700 bg-gray-900 text-gray-400 hover:text-white'}"
			>
				{autoRefresh ? '자동 새로고침 ON' : '자동 새로고침 OFF'}
			</button>
			<button onclick={load} class="text-xs text-gray-400 hover:text-white transition-colors px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600">새로고침</button>
		</div>
	</div>

	{#if loading}
		<LoadingSkeleton variant="table" rows={5} />
	{:else}
		<!-- Compute (Nova) -->
		<div class="mb-8">
			<div class="flex items-center gap-2 mb-3">
				<h2 class="text-lg font-semibold text-white">Compute (Nova)</h2>
				<span class="text-xs px-2 py-0.5 rounded bg-blue-900/30 text-blue-400">{computeServices.length}</span>
			</div>
			{#if computeServices.length === 0}
				<div class="text-gray-600 text-sm">서비스 없음</div>
			{:else}
				<div class="overflow-x-auto">
					<table class="w-full text-sm">
						<thead>
							<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
								<th class="text-left py-2 pr-4">Binary</th>
								<th class="text-left py-2 pr-4">Host</th>
								<th class="text-left py-2 pr-4">Zone</th>
								<th class="text-left py-2 pr-4">Status</th>
								<th class="text-left py-2 pr-4">State</th>
								<th class="text-left py-2 pr-4">Disabled Reason</th>
								<th class="text-left py-2">Updated</th>
							</tr>
						</thead>
						<tbody>
							{#each computeServices as s (s.id || s.binary + s.host)}
								<tr class="border-b border-gray-800/50 text-xs">
									<td class="py-2 pr-4 text-white font-mono">{s.binary}</td>
									<td class="py-2 pr-4 text-gray-300">{s.host}</td>
									<td class="py-2 pr-4 text-gray-400">{s.zone}</td>
									<td class="py-2 pr-4">
										<span class="px-1.5 py-0.5 rounded text-xs font-medium {s.status === 'enabled' ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}">{s.status}</span>
									</td>
									<td class="py-2 pr-4">
										<span class="px-1.5 py-0.5 rounded text-xs font-medium {s.state === 'up' ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}">{s.state}</span>
									</td>
									<td class="py-2 pr-4 text-gray-500">{s.disabled_reason || '-'}</td>
									<td class="py-2 text-gray-500">{s.updated_at?.slice(0, 19).replace('T', ' ') ?? '-'}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</div>

		<!-- Block Storage (Cinder) -->
		<div class="mb-8">
			<div class="flex items-center gap-2 mb-3">
				<h2 class="text-lg font-semibold text-white">Block Storage (Cinder)</h2>
				<span class="text-xs px-2 py-0.5 rounded bg-blue-900/30 text-blue-400">{blockStorageServices.length}</span>
			</div>
			{#if blockStorageServices.length === 0}
				<div class="text-gray-600 text-sm">서비스 없음</div>
			{:else}
				<div class="overflow-x-auto">
					<table class="w-full text-sm">
						<thead>
							<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
								<th class="text-left py-2 pr-4">Binary</th>
								<th class="text-left py-2 pr-4">Host</th>
								<th class="text-left py-2 pr-4">Zone</th>
								<th class="text-left py-2 pr-4">Status</th>
								<th class="text-left py-2 pr-4">State</th>
								<th class="text-left py-2 pr-4">Disabled Reason</th>
								<th class="text-left py-2">Updated</th>
							</tr>
						</thead>
						<tbody>
							{#each blockStorageServices as s (s.id || s.binary + s.host)}
								<tr class="border-b border-gray-800/50 text-xs">
									<td class="py-2 pr-4 text-white font-mono">{s.binary}</td>
									<td class="py-2 pr-4 text-gray-300">{s.host}</td>
									<td class="py-2 pr-4 text-gray-400">{s.zone}</td>
									<td class="py-2 pr-4">
										<span class="px-1.5 py-0.5 rounded text-xs font-medium {s.status === 'enabled' ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}">{s.status}</span>
									</td>
									<td class="py-2 pr-4">
										<span class="px-1.5 py-0.5 rounded text-xs font-medium {s.state === 'up' ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}">{s.state}</span>
									</td>
									<td class="py-2 pr-4 text-gray-500">{s.disabled_reason || '-'}</td>
									<td class="py-2 text-gray-500">{s.updated_at?.slice(0, 19).replace('T', ' ') ?? '-'}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</div>

		<!-- Network (Neutron) -->
		<div class="mb-8">
			<div class="flex items-center gap-2 mb-3">
				<h2 class="text-lg font-semibold text-white">Network (Neutron)</h2>
				<span class="text-xs px-2 py-0.5 rounded bg-blue-900/30 text-blue-400">{networkAgents.length}</span>
			</div>
			{#if networkAgents.length === 0}
				<div class="text-gray-600 text-sm">에이전트 없음</div>
			{:else}
				<div class="overflow-x-auto">
					<table class="w-full text-sm">
						<thead>
							<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
								<th class="text-left py-2 pr-4">Type</th>
								<th class="text-left py-2 pr-4">Binary</th>
								<th class="text-left py-2 pr-4">Host</th>
								<th class="text-left py-2 pr-4">Alive</th>
								<th class="text-left py-2 pr-4">Admin State</th>
								<th class="text-left py-2">Updated</th>
							</tr>
						</thead>
						<tbody>
							{#each networkAgents as a (a.id)}
								<tr class="border-b border-gray-800/50 text-xs">
									<td class="py-2 pr-4 text-white">{a.agent_type}</td>
									<td class="py-2 pr-4 text-gray-300 font-mono">{a.binary}</td>
									<td class="py-2 pr-4 text-gray-300">{a.host}</td>
									<td class="py-2 pr-4">
										<span class="px-1.5 py-0.5 rounded text-xs font-medium {a.alive ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}">{a.alive ? 'alive' : 'down'}</span>
									</td>
									<td class="py-2 pr-4">
										<span class="px-1.5 py-0.5 rounded text-xs font-medium {a.admin_state_up ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}">{a.admin_state_up ? 'UP' : 'DOWN'}</span>
									</td>
									<td class="py-2 text-gray-500">{a.updated_at?.slice(0, 19).replace('T', ' ') ?? '-'}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</div>
	{/if}
</div>