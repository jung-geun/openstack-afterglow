<script lang="ts">
	import type { Snippet } from 'svelte';

	interface Props {
		value?: string;
		id?: string;
		disabled?: boolean;
		required?: boolean;
		class?: string;
		children: Snippet;
		ariaLabel?: string;
		onchange?: (event: Event) => void;
	}

	let {
		value = $bindable(''),
		id,
		disabled = false,
		required = false,
		class: className = '',
		ariaLabel,
		children,
		onchange,
	}: Props = $props();
</script>

<select {id} bind:value {disabled} {required} {onchange} aria-label={ariaLabel} class="control select-input {className}">
	{@render children()}
</select>

<style>
	.control {
		width: 100%;
		border-radius: 0.5rem;
		border: 1px solid var(--color-line-2);
		background: var(--color-surface-sunken);
		color: var(--color-ink-0);
		padding: 0.5rem 0.75rem;
		font-size: 0.875rem;
		line-height: 1.4;
		transition: border-color 0.15s, box-shadow 0.15s, background 0.15s;
	}
	.control:focus {
		outline: none;
		border-color: var(--color-accent);
		box-shadow: var(--focus-ring);
	}
	.control:disabled {
		opacity: 0.55;
		cursor: not-allowed;
	}
</style>
