<script lang="ts">
	import { projectNames } from '$lib/stores/projectNames';
	import StatusChip from '$lib/components/ui/StatusChip.svelte';
	import Pagination from '$lib/components/ui/Pagination.svelte';
	import type { AdminInstance } from '$lib/types/adminInstance';

	let {
		instances,
		markerStack,
		nextMarker,
		refreshing,
		selectedIds,
		onOpen,
		onPrev,
		onNext,
		onRecover,
		onToggleSelect,
		onToggleAll,
	}: {
		instances: AdminInstance[];
		markerStack: string[];
		nextMarker: string | null;
		refreshing: boolean;
		selectedIds?: Set<string>;
		onOpen: (inst: AdminInstance) => void;
		onPrev: () => void;
		onNext: () => void;
		onRecover?: (inst: AdminInstance) => void;
		onToggleSelect?: (id: string) => void;
		onToggleAll?: () => void;
	} = $props();

	const showCheckboxes = $derived(!!onToggleSelect);
	const allSelected = $derived(
		showCheckboxes && instances.length > 0 && instances.every(i => selectedIds?.has(i.id))
	);

	let expandedError = $state<string | null>(null);
	let copiedProjectId = $state<string | null>(null);

	function copyProjectId(id: string) {
		navigator.clipboard.writeText(id).then(() => {
			copiedProjectId = id;
			setTimeout(() => { copiedProjectId = null; }, 1500);
		});
	}
</script>

<div class="overflow-x-auto">
	<table class="w-full text-sm">
		<thead>
			<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
				{#if showCheckboxes}
					<th class="py-2 pr-2 w-8">
						<input
							type="checkbox"
							checked={allSelected}
							onclick={() => onToggleAll?.()}
							class="w-4 h-4 rounded border-gray-600 bg-gray-800 accent-blue-500 cursor-pointer"
							aria-label="전체 선택"
						/>
					</th>
				{/if}
				<th class="text-left py-2 pr-4">이름</th>
				<th class="text-left py-2 pr-4">상태</th>
				<th class="text-left py-2 pr-4">Flavor</th>
				<th class="text-left py-2 pr-4">호스트</th>
				<th class="text-left py-2 pr-4">프로젝트</th>
				<th class="text-left py-2">생성일</th>
			</tr>
		</thead>
		<tbody>
			{#each instances as s (s.id)}
				<tr
					class="border-b border-gray-800/50 text-xs transition-colors {selectedIds?.has(s.id) ? 'bg-blue-900/10' : ''}"
				>
					{#if showCheckboxes}
						<td class="py-2 pr-2" onclick={(e) => e.stopPropagation()} role="none">
							<input
								type="checkbox"
								checked={selectedIds?.has(s.id) ?? false}
								onclick={() => onToggleSelect?.(s.id)}
								class="w-4 h-4 rounded border-gray-600 bg-gray-800 accent-blue-500 cursor-pointer"
								aria-label="인스턴스 선택"
							/>
						</td>
					{/if}
					<td class="p-0">
						<button type="button" onclick={() => onOpen(s)} class="block w-full py-2 pr-4 font-medium text-white hover:text-blue-400 transition-colors text-left" title={s.name || s.id}><span class="max-md:block max-md:max-w-[66vw] max-md:truncate">{s.name || s.id.slice(0, 8)}</span></button>
					</td>
					<td class="py-2 pr-4">
						<div class="flex items-center gap-1.5">
							<StatusChip status={s.status} />
							{#if s.status === 'ERROR' && s.fault}
								<button
									onclick={(e) => { e.stopPropagation(); expandedError = expandedError === s.id ? null : s.id; }}
									class="text-red-500 hover:text-red-300 text-xs underline"
									title={s.fault}
								>사유</button>
							{/if}
							{#if s.status === 'ERROR' && onRecover}
								<button
									onclick={(e) => { e.stopPropagation(); onRecover(s); }}
									class="text-amber-500 hover:text-amber-300 text-xs underline"
									title="복구 분석 및 실행"
								>복구</button>
							{/if}
						</div>
						{#if expandedError === s.id && s.fault}
							<div class="mt-1 text-red-400 bg-red-900/20 border border-red-900/50 rounded px-2 py-1 text-xs max-w-xs break-words">
								{s.fault}
							</div>
						{/if}
					</td>
					<td class="py-2 pr-4 text-gray-400">{s.flavor || '-'}</td>
					<td class="py-2 pr-4 text-gray-400">{s.host || '-'}</td>
					<td class="py-2 pr-4">
						<button
							onclick={(e) => { e.stopPropagation(); if (s.project_id) copyProjectId(s.project_id); }}
							class="text-gray-400 hover:text-blue-400 transition-colors cursor-pointer text-left"
							title={s.project_id ?? ''}
						>
							{#if copiedProjectId === s.project_id}
								<span class="text-green-400 text-xs">복사됨</span>
							{:else}
								<span class="text-xs">{s.project_id ? ($projectNames.get(s.project_id) ?? s.project_id.slice(0, 8)) : '-'}</span>
							{/if}
						</button>
					</td>
					<td class="py-2 text-gray-500">{s.created_at?.slice(0, 10) ?? '-'}</td>
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
