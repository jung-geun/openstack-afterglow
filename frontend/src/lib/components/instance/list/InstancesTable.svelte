<script lang="ts">
	import type { Instance } from '$lib/types/compute';
	import InstanceRow from './InstanceRow.svelte';
	import SelectionCheckbox from '$lib/components/ui/SelectionCheckbox.svelte';

	let {
		instances,
		underutilized = {},
		selectedIds,
		selectableIds,
		selectionDisabled,
		onSelect,
		onAction,
		onToggleSelect,
		onToggleAll,
	}: {
		instances: Instance[];
		underutilized?: Record<string, boolean>;
		selectedIds: ReadonlySet<string>;
		selectableIds: ReadonlySet<string>;
		selectionDisabled: boolean;
		onSelect: (id: string) => void;
		onAction: (kind: 'console' | 'shelve' | 'unshelve' | 'delete', instance: Instance) => Promise<void>;
		onToggleSelect: (id: string) => void;
		onToggleAll: () => void;
	} = $props();

	const allSelected = $derived(
		selectableIds.size > 0 && [...selectableIds].every((id) => selectedIds.has(id))
	);
	const hasSelection = $derived(selectedIds.size > 0);
	const partiallySelected = $derived(hasSelection && !allSelected);
</script>

<div class="overflow-x-auto">
	<div class="selection-table bg-[#0B1220] border border-gray-800 rounded-[10px] overflow-hidden" class:has-selection={hasSelection}>
		<div class="grid grid-cols-[36px_1fr_0px_0px_1fr_0px_0px_0px] sm:grid-cols-[36px_1.2fr_130px_0px_1.5fr_0px_0px_32px] md:grid-cols-[36px_1.2fr_130px_1.2fr_1.5fr_0px_0px_32px] lg:grid-cols-[36px_1.2fr_130px_1.2fr_1.5fr_80px_80px_32px] px-4 py-2.5 border-b border-gray-800 text-[11px] uppercase tracking-wider text-gray-500 font-medium">
			<div class="flex items-center">
				<SelectionCheckbox
					checked={allSelected}
					indeterminate={partiallySelected}
					disabled={selectionDisabled || selectableIds.size === 0}
					onclick={onToggleAll}
					ariaLabel="전체 선택"
				/>
			</div>
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
				selected={selectedIds.has(inst.id)}
				selectable={selectableIds.has(inst.id)}
				{selectionDisabled}
				{onSelect}
				{onAction}
				onToggleSelect={() => onToggleSelect(inst.id)}
			/>
		{/each}
	</div>
</div>

