<script lang="ts">
	import type { Snippet } from 'svelte';
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
	<div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl">
		<h2 class="text-lg font-semibold text-white mb-5">{title}</h2>
		{@render children()}
		<div class="flex justify-end gap-3 mt-6">
			{#if actions}
				{@render actions()}
			{:else}
				<button onclick={close} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">{cancelLabel}</button>
				{#if onSubmit}
					<button onclick={onSubmit} disabled={submitting} class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg disabled:opacity-30">{submitting ? '처리 중...' : submitLabel}</button>
				{/if}
			{/if}
		</div>
	</div>
</Modal>
