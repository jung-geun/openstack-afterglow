<script lang="ts">
	import type { SwiftContainer } from '$lib/types/resources';
	import { formatStorage } from '$lib/utils/format';

	let {
		container,
		deletingId,
		onDelete,
	}: {
		container: SwiftContainer;
		deletingId: string | null;
		onDelete: (name: string) => Promise<void>;
	} = $props();
</script>

<tr class="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors {container.is_quarantine ? 'bg-amber-950/20' : ''}">
	<td class="py-3 px-4">
		<a
			href="/admin/object-storage/{encodeURIComponent(container.name)}{container.project_id ? `?project_id=${encodeURIComponent(container.project_id)}` : ''}"
			class="text-indigo-400 hover:text-indigo-300 font-medium"
		>{container.name}</a>
		{#if container.is_quarantine}
			<span
				class="ml-2 inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-medium rounded border border-amber-800 bg-amber-950/50 text-amber-400"
				title="업로드 검증 중인 파일이 임시로 격리되는 시스템 버킷입니다. 검증 통과 시 원본 버킷으로 자동 이동됩니다."
			>
				격리용
			</span>
		{/if}
	</td>
	<td class="py-3 px-4 text-gray-400 text-xs font-mono">
		{container.project_name || container.project_id?.slice(0, 8) || '—'}
	</td>
	<td class="py-3 px-4 text-gray-300">{container.count}</td>
	<td class="py-3 px-4 text-gray-300">{formatStorage(Math.round(container.bytes / 1073741824))}</td>
	<td class="py-3 px-4 text-right">
		<button
			onclick={(e) => { e.stopPropagation(); onDelete(container.name); }}
			disabled={deletingId === container.name}
			class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-1 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors"
		>{deletingId === container.name ? '삭제 중...' : '삭제'}</button>
	</td>
</tr>
