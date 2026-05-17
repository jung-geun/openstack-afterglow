<script lang="ts">
	let { paths }: { paths: string[] } = $props();

	let copiedIndex = $state<number | null>(null);

	async function copyPath(path: string, index: number) {
		await navigator.clipboard.writeText(path);
		copiedIndex = index;
		setTimeout(() => (copiedIndex = null), 2000);
	}
</script>

{#if paths.length > 0}
	<div class="bg-gray-900 border border-gray-800 rounded-lg p-6 mb-4">
		<h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-4">
			Export Locations
		</h2>
		<div class="space-y-2">
			{#each paths as path, i}
				<div class="flex items-center gap-2">
					<code
						class="flex-1 text-xs text-gray-300 bg-gray-800 px-3 py-2 rounded font-mono break-all"
					>
						{path}
					</code>
					<button
						onclick={() => copyPath(path, i)}
						class="shrink-0 text-xs px-2 py-1.5 rounded border transition-colors {copiedIndex === i
							? 'border-green-700 text-green-400'
							: 'border-gray-700 text-gray-400 hover:text-gray-200 hover:border-gray-500'}"
					>
						{copiedIndex === i ? '복사됨' : '복사'}
					</button>
				</div>
			{/each}
		</div>
	</div>
{/if}
