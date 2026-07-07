<script lang="ts">
	import type { Snippet } from 'svelte';
	import Button from './Button.svelte';
	import Card from './Card.svelte';
	import Modal from './Modal.svelte';

	interface Props {
		open: boolean;
		title: string;
		onClose?: () => void;
		onSubmit?: () => void;
		submitLabel?: string;
		cancelLabel?: string;
		submitting?: boolean;
		children: Snippet;
		actions?: Snippet;
	}

	let {
		open = $bindable(false),
		title,
		onClose,
		onSubmit,
		submitLabel = '확인',
		cancelLabel = '취소',
		submitting = false,
		children,
		actions,
	}: Props = $props();

	function close() {
		open = false;
		onClose?.();
	}
</script>

<Modal bind:open {onClose}>
	<Card surface="modal" padding="lg" class="form-modal-card">
		<h2 class="form-modal-title">{title}</h2>
		{@render children()}
		<div class="form-modal-actions">
			{#if actions}
				{@render actions()}
			{:else}
				<Button onclick={close} variant="secondary">{cancelLabel}</Button>
				{#if onSubmit}
					<Button onclick={onSubmit} disabled={submitting} variant="accent">{submitting ? '처리 중...' : submitLabel}</Button>
				{/if}
			{/if}
		</div>
	</Card>
</Modal>

<style>
	.form-modal-card {
		width: min(100% - 2rem, 28rem);
		margin-inline: 1rem;
	}
	.form-modal-title {
		margin: 0 0 1.25rem;
		font-size: 1.125rem;
		font-weight: 600;
		color: var(--color-ink-0);
	}
	.form-modal-actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.75rem;
		margin-top: 1.5rem;
	}
</style>
