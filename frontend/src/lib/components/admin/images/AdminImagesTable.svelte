<script lang="ts">
	import StatusChip from '$lib/components/ui/StatusChip.svelte';
	import Pagination from '$lib/components/ui/Pagination.svelte';
	import { projectNames } from '$lib/stores/projectNames';
	import type { AdminImage } from '$lib/types/adminImage';
	import { visibilityColor } from '$lib/types/adminImage';

	let {
		images,
		selectedImageId,
		togglingId,
		markerStack,
		nextMarker,
		onOpenDetail,
		onEdit,
		onToggleActivation,
		onDelete,
		onPrev,
		onNext,
	}: {
		images: AdminImage[];
		selectedImageId: string | null;
		togglingId: string | null;
		markerStack: string[];
		nextMarker: string | null;
		onOpenDetail: (img: AdminImage) => void;
		onEdit: (img: AdminImage) => void;
		onToggleActivation: (img: AdminImage) => void;
		onDelete: (img: AdminImage) => void;
		onPrev: () => void;
		onNext: () => void;
	} = $props();

	function formatSize(bytes: number): string {
		if (!bytes) return '-';
		if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(1)} GB`;
		if (bytes >= 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(0)} MB`;
		return `${bytes} B`;
	}
</script>

<div class="overflow-x-auto">
	<table class="w-full text-sm">
		<thead>
			<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
				<th class="text-left py-2 pr-4">이름</th>
				<th class="text-left py-2 pr-4">상태</th>
				<th class="text-left py-2 pr-4">공개 범위</th>
				<th class="text-left py-2 pr-4">크기</th>
				<th class="text-left py-2 pr-4">포맷</th>
				<th class="text-left py-2 pr-4">프로젝트</th>
				<th class="text-left py-2 pr-4">생성일</th>
				<th class="text-right py-2">액션</th>
			</tr>
		</thead>
		<tbody>
			{#each images as img (img.id)}
				<tr
					class="border-b border-gray-800/50 text-xs transition-colors {selectedImageId === img.id ? 'bg-gray-800/50' : ''}"
				>
					<td class="p-0">
						<button type="button" onclick={() => onOpenDetail(img)} class="block w-full py-2 pr-4 text-white hover:text-blue-400 transition-colors text-left" title={img.name || img.id}>
							<span class="max-md:block max-md:max-w-[66vw] max-md:truncate">{img.name || img.id.slice(0, 12)}</span>
							{#if img.os_distro}
								<div class="text-gray-500 text-xs mt-0.5">{img.os_distro}</div>
							{/if}
						</button>
					</td>
					<td class="py-2 pr-4">
						<StatusChip status={img.status} />
					</td>
					<td class="py-2 pr-4">
						<span class="px-1.5 py-0.5 rounded text-xs {visibilityColor[img.visibility] ?? 'text-gray-400 bg-gray-800'}">{img.visibility}</span>
					</td>
					<td class="py-2 pr-4 text-gray-400">{formatSize(img.size)}</td>
					<td class="py-2 pr-4 text-gray-400">{img.disk_format || '-'}</td>
					<td class="py-2 pr-4 text-gray-400">
						{img.owner ? ($projectNames.get(img.owner) ?? img.owner.slice(0, 8)) : '-'}
					</td>
					<td class="py-2 pr-4 text-gray-500">{img.created_at ? img.created_at.slice(0, 10) : '-'}</td>
					<td class="py-2 text-right" onclick={(e) => e.stopPropagation()}>
						<div class="flex items-center justify-end gap-2">
							{#if img.status === 'active' || img.status === 'deactivated'}
								<button
									onclick={() => onToggleActivation(img)}
									disabled={togglingId === img.id}
									class="text-xs {img.status === 'active' ? 'text-orange-400 hover:text-orange-300' : 'text-green-400 hover:text-green-300'} disabled:opacity-40"
								>
									{togglingId === img.id ? '...' : img.status === 'active' ? '비활성화' : '활성화'}
								</button>
							{/if}
							<button onclick={() => onEdit(img)} class="text-blue-400 hover:text-blue-300 text-xs">수정</button>
							{#if !img.protected}
								<button onclick={() => onDelete(img)} class="text-red-400 hover:text-red-300 text-xs">삭제</button>
							{/if}
						</div>
					</td>
				</tr>
			{/each}
		</tbody>
	</table>
</div>
<Pagination
	page={markerStack.length + 1}
	hasPrev={markerStack.length > 0}
	hasNext={!!nextMarker}
	{onPrev}
	{onNext}
/>
