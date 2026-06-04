<script lang="ts">
	import type { ShareSnapshot } from '$lib/types/fileStorage';
	import StatusChip from '$lib/components/ui/StatusChip.svelte';

	let {
		snapshots,
		deleting,
		onDelete,
	}: {
		snapshots: ShareSnapshot[];
		deleting: string | null;
		onDelete: (id: string, name: string) => Promise<void>;
	} = $props();
</script>

<div class="overflow-x-auto">
	<table class="w-full text-sm">
		<thead>
			<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
				<th class="text-left py-3 pr-6">이름</th>
				<th class="text-left py-3 pr-6">상태</th>
				<th class="text-left py-3 pr-4">크기</th>
				<th class="text-left py-3 pr-6">파일 스토리지 ID</th>
				<th class="text-left py-3 pr-6">설명</th>
				<th class="text-left py-3 pr-6">생성일</th>
				<th class="text-right py-3">액션</th>
			</tr>
		</thead>
		<tbody>
			{#each snapshots as snap (snap.id)}
				<tr class="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
					<td class="py-3 pr-6 font-medium text-white">{snap.name || snap.id.slice(0, 8)}</td>
					<td class="py-3 pr-6"><StatusChip status={snap.status} /></td>
					<td class="py-3 pr-4 text-gray-400 text-xs">{snap.size > 0 ? `${snap.size} GB` : '-'}</td>
					<td class="py-3 pr-6 font-mono text-xs text-gray-400">{snap.share_id.slice(0, 12)}...</td>
					<td class="py-3 pr-6 text-xs text-gray-500">{snap.description || '-'}</td>
					<td class="py-3 pr-6 text-xs text-gray-500">{snap.created_at ? snap.created_at.split('T')[0] : '-'}</td>
					<td class="py-3 text-right">
						<button
							onclick={() => onDelete(snap.id, snap.name)}
							disabled={deleting === snap.id}
							class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-1 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors"
						>{deleting === snap.id ? '삭제 중...' : '삭제'}</button>
					</td>
				</tr>
			{/each}
		</tbody>
	</table>
</div>
