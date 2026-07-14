<script lang="ts">
	import type { Snippet } from 'svelte';
	import PlateGraphic from './PlateGraphic.svelte';
	import type { PlateName } from './plateGraphics';

	interface Props {
		class?: string;
		name: PlateName;
		alt: string;
		fit?: 'cover' | 'contain';
		children?: Snippet;
	}

	let { class: className = '', name, alt, fit = 'contain', children }: Props = $props();
</script>

<figure class={className}>
	<PlateGraphic {name} {alt} {fit} />
	{#if children}
		<figcaption>{@render children()}</figcaption>
	{/if}
</figure>

<style>
	figure {
		position: relative;
	}
</style>
