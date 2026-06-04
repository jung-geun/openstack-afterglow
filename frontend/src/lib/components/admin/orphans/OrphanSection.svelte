<script lang="ts" generics="T extends { id: string }">
	import type { Snippet } from 'svelte';

	let {
		title,
		items,
		selected = $bindable(new Set<string>()),
		emptyMessage,
		headerNote,
		headers,
		row,
		onCleanup,
	}: {
		title: string;
		items: T[];
		selected?: Set<string>;
		emptyMessage: string;
		headerNote?: Snippet;
		headers: Snippet;
		row: Snippet<[T]>;
		onCleanup: () => void;
	} = $props();

	function toggle(id: string) {
		const next = new Set(selected);
		if (next.has(id)) next.delete(id);
		else next.add(id);
		selected = next;
	}

	function toggleAll() {
		if (selected.size === items.length) selected = new Set();
		else selected = new Set(items.map((i) => i.id));
	}
</script>

<section class="mb-8">
	<div class="flex items-center justify-between mb-3">
		<h2 class="text-base font-semibold text-white">{title} ({items.length})</h2>
		<button
			onclick={onCleanup}
			disabled={selected.size === 0}
			class="px-3 py-1.5 bg-red-600 hover:bg-red-500 text-white text-xs font-medium rounded-lg disabled:opacity-30"
		>
			선택 {selected.size}개 정리
		</button>
	</div>

	{@render headerNote?.()}

	{#if items.length === 0}
		<div class="text-xs text-gray-500 bg-gray-900 border border-gray-800 rounded-lg p-4">
			{emptyMessage}
		</div>
	{:else}
		<div class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
						<th class="text-left py-2 pr-4 w-8">
							<input
								type="checkbox"
								checked={selected.size === items.length && items.length > 0}
								onchange={toggleAll}
							/>
						</th>
						{@render headers()}
					</tr>
				</thead>
				<tbody>
					{#each items as item (item.id)}
						<tr class="border-b border-gray-800/50 text-xs hover:bg-gray-800/30 transition-colors">
							<td class="py-2 pr-4">
								<input
									type="checkbox"
									checked={selected.has(item.id)}
									onchange={() => toggle(item.id)}
								/>
							</td>
							{@render row(item)}
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</section>
