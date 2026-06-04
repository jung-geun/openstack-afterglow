<script lang="ts">
	import { KNOWN_DISTROS, osLabel } from '$lib/utils/imageOs';

	let {
		distroFilter = $bindable('all'),
		counts,
	}: {
		distroFilter?: string;
		counts: Record<string, number>;
	} = $props();
</script>

<div class="flex flex-wrap gap-2 mb-5">
	{#each [['all', '전체'], ...KNOWN_DISTROS.map(d => [d, osLabel(d)]), ['other', '기타']] as [key, label]}
		{@const count = counts[key] ?? 0}
		{#if count > 0 || key === 'all'}
			<button
				onclick={() => distroFilter = key}
				class="px-3 py-1 rounded-full text-xs font-medium transition-colors {distroFilter === key ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-white'}"
			>
				{label} {count > 0 ? `(${count})` : ''}
			</button>
		{/if}
	{/each}
</div>
