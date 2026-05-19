<script lang="ts">
	import type { AdminNetwork } from '$lib/types/networks';

	let {
		networks,
		onRowClick,
		onEdit,
		onDelete,
	}: {
		networks: AdminNetwork[];
		onRowClick: (id: string) => void;
		onEdit: (n: AdminNetwork) => void;
		onDelete: (n: AdminNetwork) => void;
	} = $props();
</script>

<div class="overflow-x-auto">
	<table class="w-full text-sm">
		<thead>
			<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
				<th class="text-left py-2 pr-4">이름</th>
				<th class="text-left py-2 pr-4">상태</th>
				<th class="text-left py-2 pr-4">유형</th>
				<th class="text-left py-2 pr-4">서브넷</th>
				<th class="text-left py-2">액션</th>
			</tr>
		</thead>
		<tbody>
			{#each networks as n (n.id)}
				<tr
					onclick={() => onRowClick(n.id)}
					class="border-b border-gray-800/50 text-xs hover:bg-gray-800/30 transition-colors cursor-pointer"
				>
					<td class="py-2 pr-4 text-white">{n.name || n.id.slice(0, 8)}</td>
					<td class="py-2 pr-4 {n.status === 'ACTIVE' ? 'text-green-400' : 'text-gray-400'}">{n.status}</td>
					<td class="py-2 pr-4">
						{#if n.is_external}<span class="px-1.5 py-0.5 bg-orange-900/30 text-orange-300 rounded text-xs mr-1">외부</span>{/if}
						{#if n.is_shared}<span class="px-1.5 py-0.5 bg-blue-900/30 text-blue-300 rounded text-xs">공유</span>{/if}
						{#if !n.is_external && !n.is_shared}<span class="text-gray-500">내부</span>{/if}
					</td>
					<td class="py-2 pr-4 text-gray-500">{n.subnets.length}개</td>
					<td class="py-2" onclick={(e) => e.stopPropagation()}>
						<div class="flex items-center gap-1">
							<button
								onclick={() => onEdit(n)}
								class="px-2 py-0.5 text-xs bg-gray-700 hover:bg-gray-600 text-gray-300 rounded"
							>수정</button>
							<button
								onclick={() => onDelete(n)}
								class="px-2 py-0.5 text-xs bg-red-900/30 hover:bg-red-900/50 text-red-400 rounded"
							>삭제</button>
						</div>
					</td>
				</tr>
			{/each}
		</tbody>
	</table>
</div>
<div class="mt-3 text-xs text-gray-600">총 {networks.length}개 네트워크</div>
