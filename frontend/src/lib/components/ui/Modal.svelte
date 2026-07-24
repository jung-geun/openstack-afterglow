<script lang="ts">
	import type { Snippet } from 'svelte';

	interface Props {
		open: boolean;
		onClose?: () => void;
		dismissible?: boolean;
		children: Snippet;
	}

	let { open = $bindable(false), onClose, dismissible = true, children }: Props = $props();

	function close() {
		if (!dismissible) return;
		open = false;
		onClose?.();
	}
</script>

{#if open}
	<div
		class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
		onclick={close}
		onkeydown={(e) => e.key === 'Escape' && close()}
		role="dialog"
		aria-modal="true"
		tabindex="-1"
	>
		<div onclick={(e) => e.stopPropagation()}>
			{@render children()}
		</div>
	</div>
{/if}
