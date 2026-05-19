<script lang="ts">
	import { useFileStorageDetailController } from '$lib/stores/fileStorageDetailController.svelte';

	const s = useFileStorageDetailController();
</script>

<div class="bg-gray-900 border border-gray-800 rounded-lg p-5 mb-4">
	<h3 class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">Export Locations</h3>
	<div class="space-y-2">
		{#each s.fileStorage!.export_locations as path, i}
			<div class="flex items-center gap-2">
				<code class="flex-1 text-xs text-gray-300 bg-gray-800 px-3 py-2 rounded font-mono break-all">{path}</code>
				<button
					onclick={() => s.copyPath(path, i)}
					class="shrink-0 text-xs px-2 py-1.5 rounded border transition-colors {s.copiedIndex === i
						? 'border-green-700 text-green-400'
						: 'border-gray-700 text-gray-400 hover:text-gray-200 hover:border-gray-500'}"
				>
					{s.copiedIndex === i ? '복사됨' : '복사'}
				</button>
			</div>
		{/each}
	</div>
</div>
