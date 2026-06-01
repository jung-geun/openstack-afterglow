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
		onOpen,
		onPrev,
		onNext,
	}: {
		instances: AdminInstance[];
		markerStack: string[];
		nextMarker: string | null;
		refreshing: boolean;
		onOpen: (inst: AdminInstance) => void;
		onPrev: () => void;
		onNext: () => void;
	} = $props();

	let expandedError = $state<string | null>(null);
	let copiedProjectId = $state<string | null>(null);

	function copyProjectId(id: string) {
		navigator.clipboard.writeText(id).then(() => {
			copiedProjectId = id;
			setTimeout(() => { copiedProjectId = null; }, 1500);
		});
	}
</script>

<div class="overflow-x-auto" class:opacity-60={refreshing} class:pointer-events-none={refreshing}>
	<table class="w-full text-sm">
		<thead>
			<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
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
					onclick={() => onOpen(s)}
					class="border-b border-gray-800/50 text-xs hover:bg-gray-800/50 transition-colors cursor-pointer"
				>
					<td class="py-2 pr-4 text-white">{s.name || s.id.slice(0, 8)}</td>
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
