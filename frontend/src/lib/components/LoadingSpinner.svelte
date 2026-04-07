<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { HTMLAttributes } from 'svelte/elements';

	interface Props extends HTMLAttributes<HTMLDivElement> {
		size?: 'sm' | 'md' | 'lg';
		color?: 'white' | 'blue' | 'gray';
		children?: Snippet;
	}

	let { size = 'md', color = 'white', children, ...restProps }: Props = $props();

	const sizeClasses = {
		sm: 'w-4 h-4 border-2',
		md: 'w-6 h-6 border-2',
		lg: 'w-8 h-8 border-3',
	};

	const colorClasses = {
		white: 'border-white/30 border-t-white',
		blue: 'border-blue-500/30 border-t-blue-400',
		gray: 'border-gray-500/30 border-t-gray-400',
	};
</script>

<div class="inline-flex items-center gap-2" {...restProps}>
	<div
		class="animate-spin rounded-full {sizeClasses[size]} {colorClasses[color]}"
		aria-hidden="true"
	></div>
	{#if children}
		{@render children()}
	{/if}
</div>