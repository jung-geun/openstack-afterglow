<script lang="ts">
	import type { Snippet } from 'svelte';

	interface Props {
		class?: string;
		src: string;
		alt: string;
		lazy?: boolean;
		children?: Snippet;
	}

	let { class: className = '', src, alt, lazy = true, children }: Props = $props();
	let isBroken = $state(false);

	function handleImageError() {
		isBroken = true;
	}
</script>

<figure
	class={className}
	class:is-broken={isBroken}
	data-fallback-label={isBroken ? `${alt} 이미지를 불러오지 못했습니다.` : undefined}
>
	<img
		src={src}
		alt={alt}
		decoding="async"
		loading={lazy ? 'lazy' : undefined}
		onerror={handleImageError}
	/>
	{#if children}
		<figcaption>{@render children()}</figcaption>
	{/if}
</figure>

<style>
	figure {
		position: relative;
	}

	figure.is-broken::after {
		content: attr(data-fallback-label);
		position: absolute;
		inset: 12px;
		display: grid;
		place-items: center;
		padding: 18px;
		border: 1px dotted color-mix(in oklab, var(--color-line), transparent 34%);
		color: var(--color-ink-1);
		background: color-mix(in oklab, var(--color-surface-raised), transparent 8%);
		text-align: center;
		word-break: keep-all;
	}

	figure.is-broken img {
		opacity: 0.12;
	}
</style>
