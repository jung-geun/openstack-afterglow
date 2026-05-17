<script lang="ts">
	let { metadata }: { metadata: Record<string, string> } = $props();
</script>

{#if Object.keys(metadata).length > 0}
	<div class="bg-gray-900 border border-gray-800 rounded-lg p-6">
		<h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-4">메타데이터</h2>
		<table class="w-full text-sm">
			<tbody>
				{#each Object.entries(metadata) as [k, v]}
					<tr class="border-b border-gray-800/50">
						<td class="py-2 pr-4 text-gray-500 text-xs w-1/3">{k}</td>
						<td class="py-2 text-gray-300 font-mono text-xs break-all">{v}</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
{/if}
