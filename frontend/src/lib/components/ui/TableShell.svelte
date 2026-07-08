<script module lang="ts">
	export type TableDensity = 'compact' | 'normal';
</script>

<script lang="ts">
	import type { Snippet } from 'svelte';
	interface Props {
		density?: TableDensity;
		stickyHeader?: boolean;
		class?: string;
		children: Snippet;
	}

	let { density = 'normal', stickyHeader = false, class: className = '', children }: Props = $props();
</script>

<div class="table-shell table-density-{density} {className}" class:table-sticky={stickyHeader}>
	{@render children()}
</div>

<style>
	.table-shell {
		overflow-x: auto;
		border: 1px solid var(--color-line);
		border-radius: 0.875rem;
		background: var(--color-surface-raised);
	}
	.table-shell :global(table) {
		width: 100%;
		border-collapse: collapse;
	}
	.table-shell :global(thead) {
		background: var(--color-surface-sunken);
		color: var(--color-ink-2);
	}
	.table-shell :global(th),
	.table-shell :global(td) {
		border-bottom: 1px solid var(--color-line);
		text-align: left;
	}
	.table-density-normal :global(th),
	.table-density-normal :global(td) { padding: 0.75rem 1rem; }
	.table-density-compact :global(th),
	.table-density-compact :global(td) { padding: 0.5rem 0.75rem; }
	.table-shell :global(tbody tr:hover) { background: color-mix(in oklab, var(--color-surface-sunken) 55%, transparent); }
	.table-sticky :global(thead) {
		position: sticky;
		top: 0;
		z-index: 2;
	}
</style>
