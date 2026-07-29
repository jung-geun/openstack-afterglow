<script lang="ts">
	import { OS_LOGOS, OS_EMOJI, osLabel } from '$lib/utils/imageOs';
	import StatusChip from '$lib/components/ui/StatusChip.svelte';
	import type { ImageInfo } from '$lib/types/compute';
	import SelectionCheckbox from '$lib/components/ui/SelectionCheckbox.svelte';

	let {
		img,
		isOwner,
		toggling,
		deleting,
		selected = false,
		selectable = false,
		selectionDisabled = false,
		onSelect,
		onToggleSelect,
		onToggleActivation,
		onEdit,
		onDelete,
	}: {
		img: ImageInfo;
		isOwner: boolean;
		toggling: boolean;
		deleting: boolean;
		selected?: boolean;
		selectable?: boolean;
		selectionDisabled?: boolean;
		onSelect: (id: string) => void;
		onToggleSelect: () => void;
		onToggleActivation: (img: ImageInfo) => void;
		onEdit: (img: ImageInfo) => void;
		onDelete: (id: string, name: string) => void;
	} = $props();

	function formatSize(bytes: number | null): string {
		if (!bytes) return '-';
		const gb = bytes / 1024 / 1024 / 1024;
		return gb >= 1 ? `${Math.round(gb * 10) / 10} GB` : `${Math.round(bytes / 1024 / 1024)} MB`;
	}
</script>

<article
	class="resource-selection-surface bg-gray-900 border border-gray-800 rounded-2xl p-4 flex flex-col gap-3 hover:border-gray-600 transition-colors"
	data-selected={selected}
>
	<!-- Header: selection + icon + detail -->
	<div class="flex items-center gap-2.5">
		<SelectionCheckbox
			checked={selected}
			disabled={!selectable || selectionDisabled}
			unavailable={!selectable}
			title={!selectable ? '현재 프로젝트 소유 이미지만 선택할 수 있습니다.' : undefined}
			onclick={onToggleSelect}
			ariaLabel={`${img.name} 선택`}
		/>
		<div class="w-10 h-10 rounded-lg bg-gray-800 border border-gray-700 flex items-center justify-center overflow-hidden shrink-0">
			{#if img.os_distro && OS_LOGOS[img.os_distro]}
				<img src={OS_LOGOS[img.os_distro]} alt={img.os_distro} class="w-6 h-6 object-contain" />
			{:else if img.os_distro && OS_EMOJI[img.os_distro]}
				<span class="text-lg">{OS_EMOJI[img.os_distro]}</span>
			{:else}
				<span class="text-lg">💿</span>
			{/if}
		</div>
		<button
			type="button"
			class="flex-1 min-w-0 text-left"
			onclick={() => onSelect(img.id)}
		>
			<div class="text-white text-[13px] font-medium truncate font-mono">{img.name}</div>
			<div class="text-[10px] text-gray-500 mt-0.5 font-mono">tag: {img.tag ?? 'latest'}</div>
			<div class="text-[11px] text-gray-500 mt-0.5">{img.os_distro ? osLabel(img.os_distro) : 'Unknown'}</div>
		</button>
	</div>

	<!-- Footer: status + visibility + size -->
	<div class="flex items-center gap-2 text-[11px]">
		<StatusChip status={img.status} />
		{#if img.visibility === 'public'}
			<span class="px-1.5 py-0.5 rounded border text-[10px] font-medium bg-blue-900/25 border-blue-800 text-blue-400">공개</span>
		{:else if img.visibility === 'shared'}
			<span class="px-1.5 py-0.5 rounded border text-[10px] font-medium bg-teal-900/25 border-teal-800 text-teal-400">공유</span>
		{:else if img.visibility === 'community'}
			<span class="px-1.5 py-0.5 rounded border text-[10px] font-medium bg-teal-900/25 border-teal-800 text-teal-400">커뮤니티</span>
		{:else}
			<span class="px-1.5 py-0.5 rounded border text-[10px] font-medium bg-gray-800/70 border-gray-700 text-gray-400">비공개</span>
		{/if}
		<span class="ml-auto text-gray-500">{formatSize(img.size ?? null)}</span>
	</div>

	<!-- Actions (own images only) -->
	{#if isOwner}
		<div class="flex items-center gap-1 pt-1 border-t border-gray-800">
			{#if img.status === 'active' || img.status === 'deactivated'}
				<button
					onclick={() => onToggleActivation(img)}
					disabled={toggling}
					class="text-[11px] {img.status === 'active' ? 'text-orange-400 hover:text-orange-300' : 'text-green-400 hover:text-green-300'} disabled:text-gray-600 transition-colors px-2 py-1 rounded hover:bg-gray-800"
				>{toggling ? '...' : img.status === 'active' ? '비활성화' : '활성화'}</button>
			{/if}
			<button
				onclick={() => onEdit(img)}
				class="text-[11px] text-blue-400 hover:text-blue-300 transition-colors px-2 py-1 rounded hover:bg-blue-900/30"
			>편집</button>
			<button
				onclick={() => onDelete(img.id, img.name)}
				disabled={deleting}
				class="text-[11px] text-red-400 hover:text-red-300 disabled:text-gray-600 transition-colors px-2 py-1 rounded hover:bg-red-900/30"
			>{deleting ? '삭제 중...' : '삭제'}</button>
		</div>
	{/if}
</article>
