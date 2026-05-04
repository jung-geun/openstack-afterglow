<script lang="ts">
	let { size = 26, inset = 3 }: { size?: number; inset?: number } = $props();
</script>

<div class="ringmark" style="--size:{size}px; --inset:{inset}px"></div>

<style>
	.ringmark {
		width: var(--size);
		height: var(--size);
		border-radius: 999px;
		background: var(--warm-grad);
		position: relative;
		flex-shrink: 0;
	}
	.ringmark::after {
		content: "";
		position: absolute;
		inset: var(--inset);
		border-radius: 999px;
		background: var(--color-surface-base);
	}
</style>
