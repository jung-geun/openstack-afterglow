<script lang="ts">
	import type { Cluster } from '$lib/types/cluster';
	import StatusChip from '$lib/components/ui/StatusChip.svelte';

	let {
		clusters,
		deleting,
		onDelete,
		onNavigate,
	}: {
		clusters: Cluster[];
		deleting: string | null;
		onDelete: (id: string, name: string) => Promise<void>;
		onNavigate: (id: string) => void;
	} = $props();
</script>

<div class="overflow-x-auto">
	<table class="w-full text-sm">
		<thead>
			<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
				<th class="text-left py-3 pr-6">이름</th>
				<th class="text-left py-3 pr-6">상태</th>
				<th class="text-left py-3 pr-6">마스터</th>
				<th class="text-left py-3 pr-6">워커</th>
				<th class="text-left py-3 pr-6">API 주소</th>
				<th class="text-left py-3 pr-6">생성일</th>
				<th class="text-left py-3"></th>
			</tr>
		</thead>
		<tbody>
			{#each clusters as c (c.id)}
				<tr class="border-b border-gray-800/50 hover:bg-gray-800/50 transition-colors">
					<td class="py-3 pr-6">
						<button onclick={() => onNavigate(c.id)} class="font-medium text-white hover:text-blue-400 transition-colors text-left max-md:block max-md:max-w-[66vw] max-md:truncate" title={c.name}>{c.name}</button>
					</td>
					<td class="py-3 pr-6">
						<StatusChip status={c.status} />
					</td>
					<td class="py-3 pr-6 text-gray-400 text-xs">{c.master_count}</td>
					<td class="py-3 pr-6 text-gray-400 text-xs">{c.node_count}</td>
					<td class="py-3 pr-6 text-gray-400 text-xs font-mono">{c.api_address ?? '-'}</td>
					<td class="py-3 pr-6 text-gray-400 text-xs">{c.created_at?.slice(0, 10) ?? '-'}</td>
					<td class="py-3">
						<button
							onclick={() => onDelete(c.id, c.name)}
							disabled={deleting === c.id}
							class="text-xs text-red-400 hover:text-red-300 disabled:opacity-40 transition-colors"
						>
							{deleting === c.id ? '삭제 중...' : '삭제'}
						</button>
					</td>
				</tr>
			{/each}
		</tbody>
	</table>
</div>
