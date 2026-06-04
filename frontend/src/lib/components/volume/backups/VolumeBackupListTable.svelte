<script lang="ts">
	import type { VolumeBackup } from '$lib/types/volume';
	import StatusChip from '$lib/components/ui/StatusChip.svelte';
	import { formatStorage } from '$lib/utils/format';

	let {
		backups,
		deletingId,
		onRestore,
		onDelete,
	}: {
		backups: VolumeBackup[];
		deletingId: string | null;
		onRestore: (b: VolumeBackup) => void;
		onDelete: (id: string, name: string) => Promise<void>;
	} = $props();
</script>

<div class="overflow-x-auto">
	<table class="w-full text-sm">
		<thead>
			<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
				<th class="text-left py-3 pr-6">이름</th>
				<th class="text-left py-3 pr-6">상태</th>
				<th class="text-left py-3 pr-6">크기</th>
				<th class="text-left py-3 pr-6">증분</th>
				<th class="text-left py-3 pr-6">생성일</th>
				<th class="text-right py-3">액션</th>
			</tr>
		</thead>
		<tbody>
			{#each backups as backup (backup.id)}
				<tr class="border-b border-gray-800/50 hover:bg-gray-800/50 transition-colors">
					<td class="py-3 pr-6 font-medium text-white">{backup.name || backup.id.slice(0, 8)}</td>
					<td class="py-3 pr-6"><StatusChip status={backup.status} /></td>
					<td class="py-3 pr-6 text-gray-400">{formatStorage(backup.size)}</td>
					<td class="py-3 pr-6"><span class="text-xs {backup.is_incremental ? 'text-blue-400' : 'text-gray-500'}">{backup.is_incremental ? '증분' : '전체'}</span></td>
					<td class="py-3 pr-6 text-gray-400 text-xs">{backup.created_at ? new Date(backup.created_at).toLocaleDateString('ko-KR') : '-'}</td>
					<td class="py-3 text-right flex items-center justify-end gap-2">
						<button onclick={() => onRestore(backup)} class="text-blue-400 hover:text-blue-300 text-xs px-2 py-1 rounded border border-blue-900 hover:border-blue-700 transition-colors">
							복원
						</button>
						<button onclick={() => onDelete(backup.id, backup.name)} disabled={deletingId === backup.id} class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-1 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors">
							{deletingId === backup.id ? '삭제 중...' : '삭제'}
						</button>
					</td>
				</tr>
			{/each}
		</tbody>
	</table>
</div>
