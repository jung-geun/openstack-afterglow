<script lang="ts">
	import StatusChip from '$lib/components/ui/StatusChip.svelte';
	import type { K3sCluster } from '$lib/types/k3s';

	let {
		cluster,
		deleting,
		onSelect,
		onDownloadKubeconfig,
		onDelete,
	}: {
		cluster: K3sCluster;
		deleting: boolean;
		onSelect: (id: string) => void;
		onDownloadKubeconfig: (id: string, name: string) => void;
		onDelete: (id: string, name: string) => void;
	} = $props();
</script>

<div
	class="bg-gray-900 border border-gray-800 rounded-2xl p-5 transition-colors {cluster.deleted_at ? 'opacity-50' : 'cursor-pointer hover:border-gray-600'}"
	onclick={() => !cluster.deleted_at && onSelect(cluster.id)}
	role={cluster.deleted_at ? undefined : 'button'}
	tabindex={cluster.deleted_at ? undefined : 0}
	onkeydown={(e) => e.key === 'Enter' && !cluster.deleted_at && onSelect(cluster.id)}
>
	<!-- Header -->
	<div class="flex items-center gap-2.5 mb-3">
		<div class="w-[34px] h-[34px] rounded-[9px] bg-emerald-500/12 border border-emerald-500/30 text-emerald-400 flex items-center justify-center shrink-0">
			<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
				<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
			</svg>
		</div>
		<div class="flex-1 min-w-0">
			<div class="text-white font-semibold text-sm truncate {cluster.deleted_at ? 'line-through text-gray-500' : ''}">
				{cluster.name}
			</div>
			<div class="text-[11px] text-gray-500 font-mono mt-0.5">
				{cluster.k3s_version || 'k3s'}
			</div>
		</div>
		<StatusChip status={cluster.status} />
	</div>

	<!-- Info grid -->
	<div class="grid grid-cols-2 gap-2 text-xs mb-3.5">
		<div>
			<div class="text-[11px] uppercase tracking-wider font-medium text-gray-500">노드 (M+A)</div>
			<div class="text-gray-200 mt-0.5">{cluster.agent_count + 1} (1+{cluster.agent_count})</div>
		</div>
		<div>
			<div class="text-[11px] uppercase tracking-wider font-medium text-gray-500">API</div>
			<div class="text-gray-200 mt-0.5 font-mono text-xs truncate">{cluster.api_address || '—'}</div>
		</div>
		{#if cluster.deleted_at}
			<div class="col-span-2">
				<div class="text-[11px] uppercase tracking-wider font-medium text-gray-500">삭제됨</div>
				<div class="text-gray-500 mt-0.5 text-xs">{cluster.deleted_at.replace('T', ' ').slice(0, 16)}</div>
			</div>
		{:else if cluster.status_reason}
			<div class="col-span-2">
				<div class="text-[11px] text-gray-500 truncate">{cluster.status_reason}</div>
			</div>
		{/if}
	</div>

	<!-- Actions -->
	<div class="flex gap-1.5" role="none" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
		<button
			onclick={() => onDownloadKubeconfig(cluster.id, cluster.name)}
			disabled={cluster.status !== 'ACTIVE'}
			class="flex-1 text-blue-400 hover:text-blue-300 disabled:text-gray-600 text-xs px-2 py-1.5 rounded border border-blue-900 hover:border-blue-700 disabled:border-gray-700 transition-colors text-center"
		>kubeconfig</button>
		<button
			onclick={() => onSelect(cluster.id)}
			disabled={!!cluster.deleted_at}
			class="text-gray-400 hover:text-white disabled:text-gray-600 text-xs px-2 py-1.5 rounded border border-gray-700 hover:border-gray-500 disabled:border-gray-700 transition-colors"
		>상세</button>
		{#if !cluster.deleted_at}
			<button
				onclick={() => onDelete(cluster.id, cluster.name)}
				disabled={deleting || cluster.status === 'DELETING'}
				class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-1.5 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors"
			>{deleting ? '삭제 중...' : '삭제'}</button>
		{/if}
	</div>
</div>
