<script lang="ts">
	import type { K3sNodegroup } from '$lib/types/k3s';

	let {
		nodegroup,
		onEdit,
		onDelete,
	}: {
		nodegroup: K3sNodegroup;
		onEdit?: (ng: K3sNodegroup) => void;
		onDelete?: (ng: K3sNodegroup) => void;
	} = $props();

	const roleLabel = $derived(nodegroup.role === 'server' ? '서버' : '에이전트');
	const roleBadgeClass = $derived(
		nodegroup.role === 'server'
			? 'bg-purple-900/40 text-purple-400 border-purple-800'
			: 'bg-blue-900/40 text-blue-400 border-blue-800'
	);

	const runningVms = $derived(nodegroup.vms.filter(v => v.status === 'RUNNING' || v.status === 'ACTIVE').length);
	const inFlight = $derived((nodegroup.stampede_state as Record<string, number>)?.in_flight_count ?? 0);
</script>

<div class="bg-gray-800/50 border border-gray-700 rounded-lg p-3 space-y-2">
	<div class="flex items-center justify-between">
		<div class="flex items-center gap-2 flex-wrap">
			<span class="text-xs border rounded px-1.5 py-0.5 {roleBadgeClass}">{roleLabel}</span>
			<span class="text-sm font-medium text-white">{nodegroup.name}</span>
			{#if nodegroup.is_default}
				<span class="text-xs text-gray-500">(기본)</span>
			{/if}
			{#if nodegroup.stampede_enabled}
				<span class="text-xs bg-blue-900/50 text-blue-300 border border-blue-700/60 rounded px-1.5 py-0.5 leading-none">Stampede</span>
				<span class="text-xs text-gray-500">{nodegroup.min_size}–{nodegroup.max_size}</span>
				{#if inFlight > 0}
					<span class="text-xs text-yellow-400 animate-pulse">▲ +{inFlight} 프로비저닝 중</span>
				{/if}
			{/if}
		</div>
		<div class="flex items-center gap-1">
			{#if onEdit && !nodegroup.is_default}
				<button
					onclick={() => onEdit?.(nodegroup)}
					class="text-xs text-gray-400 hover:text-blue-400 px-2 py-1 rounded transition-colors"
				>수정</button>
			{/if}
			{#if onDelete && !nodegroup.is_default}
				<button
					onclick={() => onDelete?.(nodegroup)}
					class="text-xs text-gray-400 hover:text-red-400 px-2 py-1 rounded transition-colors"
				>삭제</button>
			{/if}
		</div>
	</div>

	<div class="flex items-center gap-4 text-xs text-gray-400">
		<span>노드 수: <span class="text-white">{nodegroup.node_count}</span></span>
		{#if nodegroup.vms.length > 0}
			<span>VM: <span class="text-white">{runningVms}/{nodegroup.vms.length}</span></span>
		{/if}
		{#if nodegroup.flavor_id}
			<span class="font-mono truncate max-w-32">{nodegroup.flavor_id.slice(0, 12)}...</span>
		{/if}
	</div>

	{#if Object.keys(nodegroup.labels ?? {}).length > 0}
		<div class="flex flex-wrap gap-1">
			{#each Object.entries(nodegroup.labels) as [k, v]}
				<span class="text-xs bg-gray-700 text-gray-300 rounded px-1.5 py-0.5 font-mono">{k}={v}</span>
			{/each}
		</div>
	{/if}
</div>
