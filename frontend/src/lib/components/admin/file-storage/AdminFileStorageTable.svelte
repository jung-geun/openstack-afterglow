<script lang="ts">
	import type { AdminFileStorage } from '$lib/types/fileStorage';
	import { projectNames } from '$lib/stores/projectNames';
	import { formatNumber } from '$lib/utils/format';
	import StatusChip from '$lib/components/ui/StatusChip.svelte';

	let {
		storages,
	}: {
		storages: AdminFileStorage[];
	} = $props();

	let copiedId = $state<string | null>(null);

	function copyValue(v: string) {
		navigator.clipboard.writeText(v);
		copiedId = v;
		setTimeout(() => { copiedId = null; }, 1500);
	}

	function formatDate(iso: string | null): string {
		if (!iso) return '-';
		return iso.slice(0, 10);
	}
</script>

<div class="overflow-x-auto">
	<table class="w-full text-sm">
		<thead>
			<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
				<th class="text-left py-2 pr-4">이름</th>
				<th class="text-left py-2 pr-4">상태</th>
				<th class="text-left py-2 pr-4">크기</th>
				<th class="text-left py-2 pr-4">프로토콜</th>
				<th class="text-left py-2 pr-4">유형</th>
				<th class="text-left py-2 pr-4">프로젝트</th>
				<th class="text-left py-2 pr-4">생성일</th>
				<th class="text-left py-2">Export 경로</th>
			</tr>
		</thead>
		<tbody>
			{#each storages as fs (fs.id)}
				<tr class="border-b border-gray-800/50 text-xs hover:bg-gray-800/20">
					<td class="py-2 pr-4 text-white font-medium">{fs.name || fs.id.slice(0, 8)}</td>
					<td class="py-2 pr-4"><StatusChip status={fs.status} /></td>
					<td class="py-2 pr-4 text-gray-400">{formatNumber(fs.size)} GB</td>
					<td class="py-2 pr-4">
						<span class="px-1.5 py-0.5 rounded text-xs font-medium {fs.share_proto === 'NFS' ? 'bg-blue-900/40 text-blue-300' : 'bg-purple-900/40 text-purple-300'}">{fs.share_proto}</span>
					</td>
					<td class="py-2 pr-4 text-gray-500">{fs.metadata?.union_type || '-'}</td>
					<td class="py-2 pr-4">
						{#if fs.project_id}
							<div class="flex items-center gap-1.5">
								<span class="text-gray-300">{$projectNames.get(fs.project_id) ?? fs.project_id.slice(0, 8)}</span>
								<button
									onclick={() => copyValue(fs.project_id!)}
									class="text-gray-600 hover:text-gray-400 transition-colors"
									title={fs.project_id}
								>
									{#if copiedId === fs.project_id}
										<svg class="w-3 h-3 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
									{:else}
										<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path></svg>
									{/if}
								</button>
							</div>
						{:else}
							<span class="text-gray-600">-</span>
						{/if}
					</td>
					<td class="py-2 pr-4 text-gray-400">{formatDate(fs.created_at)}</td>
					<td class="py-2 text-gray-500 font-mono">
						{#if fs.export_locations?.length > 0}
							<div class="flex items-center gap-1.5">
								<span class="truncate max-w-[200px]" title={fs.export_locations[0]}>{fs.export_locations[0]}</span>
								<button
									onclick={() => copyValue(fs.export_locations[0])}
									class="text-gray-600 hover:text-gray-400 transition-colors shrink-0"
								>
									{#if copiedId === fs.export_locations[0]}
										<svg class="w-3 h-3 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
									{:else}
										<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path></svg>
									{/if}
								</button>
							</div>
						{:else}
							<span>-</span>
						{/if}
					</td>
				</tr>
			{/each}
		</tbody>
	</table>
</div>
