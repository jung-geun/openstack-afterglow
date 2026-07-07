<script lang="ts">
	interface Props {
		checked?: boolean;
		indeterminate?: boolean;
		ariaLabel: string;
		onclick?: (event: MouseEvent) => void;
		class?: string;
	}

	let {
		checked = false,
		indeterminate = false,
		ariaLabel,
		onclick,
		class: className = '',
	}: Props = $props();

	let inputEl = $state<HTMLInputElement | null>(null);

	$effect(() => {
		if (inputEl) inputEl.indeterminate = indeterminate;
	});
</script>

<label
	class="selection-checkbox {className}"
	class:is-checked={checked}
	class:is-indeterminate={indeterminate}
>
	<input
		bind:this={inputEl}
		type="checkbox"
		checked={checked}
		aria-label={ariaLabel}
		onclick={(event) => onclick?.(event)}
	/>
	<span class="selection-box" aria-hidden="true">
		<svg class="selection-check" width="15" height="14" viewBox="0 0 15 14" fill="none">
			<path d="M2 8.36364L6.23077 12L13 2" />
		</svg>
		<span class="selection-minus"></span>
	</span>
</label>

<style>
	.selection-checkbox {
		position: relative;
		display: inline-grid;
		width: 22px;
		height: 22px;
		place-items: center;
		cursor: pointer;
		isolation: isolate;
	}

	.selection-checkbox input {
		position: absolute;
		inset: 0;
		z-index: 2;
		margin: 0;
		cursor: pointer;
		opacity: 0;
	}

	.selection-box {
		position: relative;
		display: grid;
		width: 18px;
		height: 18px;
		place-items: center;
		border: 2px solid color-mix(in oklab, var(--color-ink-3) 72%, transparent);
		border-radius: 5px;
		background: color-mix(in oklab, var(--color-surface-raised) 82%, transparent);
		box-shadow: inset 0 0 0 1px color-mix(in oklab, white 4%, transparent);
		transition:
			border-color 0.16s ease,
			background 0.16s ease,
			box-shadow 0.16s ease,
			transform 0.16s ease;
	}

	.selection-check {
		position: absolute;
		width: 13px;
		height: 12px;
		z-index: 1;
	}

	.selection-check path {
		stroke: var(--color-action-on-accent);
		stroke-width: 3;
		stroke-linecap: round;
		stroke-linejoin: round;
		stroke-dasharray: 19;
		stroke-dashoffset: 19;
		transition: stroke-dashoffset 0.22s ease 0.06s;
	}

	.selection-minus {
		width: 8px;
		height: 2px;
		border-radius: 999px;
		background: var(--color-action-on-accent);
		opacity: 0;
		transform: scaleX(0.4);
		transition:
			opacity 0.14s ease,
			transform 0.16s ease;
	}

	.selection-checkbox:hover .selection-box,
	.selection-checkbox input:focus-visible + .selection-box {
		border-color: var(--color-accent-2);
		box-shadow: var(--focus-ring);
	}

	.selection-checkbox input:focus-visible + .selection-box {
		outline: none;
	}

	.selection-checkbox.is-checked .selection-box,
	.selection-checkbox.is-indeterminate .selection-box {
		border-color: transparent;
		background: linear-gradient(135deg, var(--color-accent-2), var(--color-accent));
		box-shadow:
			0 0 0 1px color-mix(in oklab, var(--color-accent-2) 20%, transparent),
			0 6px 18px color-mix(in oklab, var(--color-accent-2) 26%, transparent);
		animation: selection-pop 0.28s ease;
	}

	.selection-checkbox.is-checked .selection-check path {
		stroke-dashoffset: 0;
	}

	.selection-checkbox.is-indeterminate .selection-minus {
		opacity: 1;
		transform: scaleX(1);
	}

	.selection-checkbox.is-indeterminate .selection-check path {
		stroke-dashoffset: 19;
		transition-delay: 0s;
	}

	.selection-checkbox input:disabled,
	.selection-checkbox input:disabled + .selection-box {
		cursor: not-allowed;
		opacity: 0.5;
	}

	@keyframes selection-pop {
		0% { transform: scale(0.88); }
		58% { transform: scale(1.08); }
		100% { transform: scale(1); }
	}

	@media (prefers-reduced-motion: reduce) {
		.selection-box,
		.selection-check path,
		.selection-minus {
			transition: none;
		}
		.selection-checkbox.is-checked .selection-box,
		.selection-checkbox.is-indeterminate .selection-box {
			animation: none;
		}
	}
</style>
