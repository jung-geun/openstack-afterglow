<script lang="ts">
	import StatusChip from '$lib/components/ui/StatusChip.svelte';
	import type { FileStorage } from '$lib/types/libraries';

	let { fileStorages }: { fileStorages: FileStorage[] } = $props();
</script>

<div class="mt-8">
	<h2 class="text-sm font-medium text-gray-400 mb-3">프리빌트 Share 목록 ({fileStorages.length})</h2>
	<div class="rounded-lg border border-gray-700 overflow-hidden">
		<table class="w-full text-sm">
			<thead class="bg-gray-800 text-gray-400 text-xs uppercase">
				<tr>
					<th class="px-4 py-3 text-left">이름</th>
					<th class="px-4 py-3 text-left">라이브러리</th>
					<th class="px-4 py-3 text-left">상태</th>
				</tr>
			</thead>
			<tbody class="divide-y divide-gray-700/50">
				{#each fileStorages as fs}
					<tr class="hover:bg-gray-800/50">
						<td class="px-4 py-3 text-gray-300 text-xs font-mono">{fs.name}</td>
						<td class="px-4 py-3 text-gray-400 text-xs">
							{fs.library_name ?? '-'}
							{#if fs.library_version}<span class="text-gray-600"> v{fs.library_version}</span>{/if}
						</td>
						<td class="px-4 py-3"><StatusChip status={fs.status} /></td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
</div>
