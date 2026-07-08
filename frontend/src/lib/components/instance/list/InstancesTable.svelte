<script lang="ts">
	import type { Instance } from '$lib/types/compute';
	import InstanceRow from './InstanceRow.svelte';
	import SelectionCheckbox from '$lib/components/ui/SelectionCheckbox.svelte';

	let {
		instances,
		underutilized = {},
		selectedIds,
		onSelect,
		onAction,
		onToggleSelect,
		onToggleAll,
	}: {
		instances: Instance[];
		underutilized?: Record<string, boolean>;
		selectedIds?: Set<string>;
		onSelect: (id: string) => void;
		onAction: (kind: 'console' | 'shelve' | 'unshelve' | 'delete', instance: Instance) => Promise<void>;
		onToggleSelect?: (id: string) => void;
		onToggleAll?: () => void;
	} = $props();

	const showCheckboxes = $derived(!!onToggleSelect);
	const allSelected = $derived(
		showCheckboxes && instances.length > 0 && instances.every(i => selectedIds?.has(i.id))
	);
	const hasSelection = $derived(showCheckboxes && instances.some(i => selectedIds?.has(i.id)));
	const partiallySelected = $derived(hasSelection && !allSelected);
</script>

<div class="overflow-x-auto">
	<div class="selection-table bg-[#0B1220] border border-gray-800 rounded-[10px] overflow-hidden" class:has-selection={hasSelection}>
		<div class="grid {showCheckboxes ? 'grid-cols-[36px_1fr_0px_0px_1fr_0px_0px_0px] sm:grid-cols-[36px_1.2fr_130px_0px_1.5fr_0px_0px_32px] md:grid-cols-[36px_1.2fr_130px_1.2fr_1.5fr_0px_0px_32px] lg:grid-cols-[36px_1.2fr_130px_1.2fr_1.5fr_80px_80px_32px]' : 'grid-cols-[1fr_0px_0px_1fr_0px_0px_0px] sm:grid-cols-[1.2fr_130px_0px_1.5fr_0px_0px_32px] md:grid-cols-[1.2fr_130px_1.2fr_1.5fr_0px_0px_32px] lg:grid-cols-[1.2fr_130px_1.2fr_1.5fr_80px_80px_32px]'} px-4 py-2.5 border-b border-gray-800 text-[11px] uppercase tracking-wider text-gray-500 font-medium">
			{#if showCheckboxes}
				<div class="selection-header-reveal flex items-center" class:is-selected={hasSelection}>
					<SelectionCheckbox
						checked={allSelected}
						indeterminate={partiallySelected}
						onclick={() => onToggleAll?.()}
						ariaLabel="전체 선택"
					/>
				</div>
			{/if}
			<div>이름</div>
			<div class="hidden sm:block">상태</div>
			<div class="hidden md:block">이미지 / 플레이버</div>
			<div>IP</div>
			<div class="hidden lg:block">라이브러리</div>
			<div class="hidden lg:block">전략</div>
			<div></div>
		</div>
		{#each instances as inst (inst.id)}
			<InstanceRow
				instance={inst}
				isUnderutilized={underutilized[inst.id] ?? false}
				isSelected={selectedIds?.has(inst.id) ?? false}
				{showCheckboxes}
				{onSelect}
				{onAction}
				onToggleSelect={onToggleSelect ? () => onToggleSelect(inst.id) : undefined}
			/>
		{/each}
	</div>
</div>

<style>
	.selection-header-reveal {
		opacity: 0;
		pointer-events: none;
		transform: translateX(-4px);
		transition:
			opacity 0.16s ease,
			transform 0.16s ease;
	}

	.selection-table:hover .selection-header-reveal,
	.selection-table:focus-within .selection-header-reveal,
	.selection-table.has-selection .selection-header-reveal,
	.selection-header-reveal.is-selected {
		opacity: 1;
		pointer-events: auto;
		transform: translateX(0);
	}
</style>
