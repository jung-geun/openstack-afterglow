<script module lang="ts">
	export interface ToggleOption {
		value: string;
		label: string;
		disabled?: boolean;
	}
</script>

<script lang="ts">
	interface Props {
		value: string;
		options: ToggleOption[];
		onchange: (value: string) => void;
		size?: 'xs' | 'sm';
		class?: string;
		ariaLabel?: string;
	}

	let {
		value,
		options,
		onchange,
		size = 'sm',
		class: className = '',
		ariaLabel
	}: Props = $props();
</script>

<div class="toggle-group toggle-{size} {className}" role="group" aria-label={ariaLabel}>
	{#each options as option}
		<button
			type="button"
			class="toggle-option"
			class:toggle-selected={option.value === value}
			disabled={option.disabled}
			aria-pressed={option.value === value}
			onclick={() => {
				if (option.value !== value && !option.disabled) onchange(option.value);
			}}
		>
			{option.label}
		</button>
	{/each}
</div>

<style>
	.toggle-group {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		padding: 0.25rem;
		border: 1px solid var(--color-line);
		border-radius: 0.625rem;
		background: var(--color-surface-sunken);
	}
	.toggle-option {
		border: 0;
		border-radius: 0.4375rem;
		background: transparent;
		color: var(--color-ink-2);
		font-weight: 500;
		cursor: pointer;
		transition: background 0.15s, color 0.15s, box-shadow 0.15s;
	}
	.toggle-xs .toggle-option { padding: 0.1875rem 0.5rem; font-size: 0.6875rem; }
	.toggle-sm .toggle-option { padding: 0.25rem 0.625rem; font-size: 0.75rem; }
	.toggle-option:hover:not(:disabled) { color: var(--color-ink-0); }
	.toggle-option:focus-visible {
		outline: none;
		box-shadow: var(--focus-ring);
	}
	.toggle-selected {
		background: var(--color-surface-raised);
		color: var(--color-ink-0);
	}
	.toggle-option:disabled {
		opacity: 0.45;
		cursor: not-allowed;
	}
</style>
