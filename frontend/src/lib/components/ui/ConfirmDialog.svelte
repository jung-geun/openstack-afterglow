<script lang="ts">
	import { dialogState } from '$lib/stores/confirm.svelte';
	import Button from './Button.svelte';
	import Card from './Card.svelte';
</script>

{#if dialogState.open}
	<div class="confirm-overlay" role="dialog" aria-modal="true">
		<Card surface="modal" padding="lg" class="confirm-card">
			<p class="confirm-message">{dialogState.message}</p>
			<div class="confirm-actions">
				<Button onclick={dialogState.reject} variant="secondary">취소</Button>
				<Button onclick={dialogState.accept} variant="danger">확인</Button>
			</div>
		</Card>
	</div>
{/if}

<svelte:window onkeydown={(e) => { if (e.key === 'Escape' && dialogState.open) dialogState.reject(); }} />

<style>
	.confirm-overlay {
		position: fixed;
		inset: 0;
		z-index: 200;
		display: flex;
		align-items: center;
		justify-content: center;
		background: color-mix(in oklab, var(--color-surface-canvas) 72%, transparent);
	}
	.confirm-card {
		width: min(100% - 2rem, 24rem);
		margin-inline: 1rem;
	}
	.confirm-message {
		margin: 0 0 1.5rem;
		white-space: pre-wrap;
		font-size: 0.875rem;
		line-height: 1.5;
		color: var(--color-ink-1);
	}
	.confirm-actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.75rem;
	}
</style>
