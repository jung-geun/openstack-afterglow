<script lang="ts">
	import type { Snippet } from 'svelte';

	let {
		value,
		label,
		valueClass = 'text-white',
		size = 'md',
		labelExtra,
	}: {
		value: number | string;
		label: string;
		valueClass?: string;
		size?: 'sm' | 'md' | 'lg';
		labelExtra?: Snippet;
	} = $props();

	const padding = { sm: 'p-2', md: 'p-3', lg: 'p-4' };
	const fontSize = { sm: 'text-lg', md: 'text-2xl', lg: 'text-2xl' };
</script>

<div class="bg-gray-800 rounded-lg text-center {padding[size]}">
	<div class="font-bold {fontSize[size]} {valueClass}">{value}</div>
	<div class="text-xs text-gray-500 mt-1">
		{label}{#if labelExtra} {@render labelExtra()}{/if}
	</div>
</div>
