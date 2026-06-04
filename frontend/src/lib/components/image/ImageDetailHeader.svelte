<script lang="ts">
	import { useImageDetailController } from '$lib/stores/imageDetailController.svelte';
	import { visibilityBadge, visibilityLabel } from '$lib/utils/format';

	interface Props {
		onClose?: () => void;
	}
	let { onClose }: Props = $props();

	const s = useImageDetailController();
</script>

<div class="flex items-start justify-between px-6 py-4 border-b border-gray-800 shrink-0">
	<div class="min-w-0 pr-4">
		{#if s.image}
			<h2 class="text-lg font-bold text-white truncate">{s.image.name}</h2>
			<div class="flex items-center gap-2 mt-1.5 flex-wrap">
				<span class="px-2 py-0.5 rounded text-xs font-medium {s.image.status === 'active' ? 'text-green-400 bg-green-900/30' : 'text-gray-400 bg-gray-800'}">
					{s.image.status}
				</span>
				<span class="px-2 py-0.5 rounded text-xs font-medium {visibilityBadge(s.image.visibility)}">
					{visibilityLabel(s.image.visibility)}
				</span>
				{#if s.image.protected}
					<span class="px-2 py-0.5 rounded text-xs font-medium text-amber-400 bg-amber-900/30">보호됨</span>
				{/if}
			</div>
		{:else if s.loading}
			<div class="h-6 w-48 bg-gray-800 rounded animate-pulse"></div>
		{/if}
	</div>
	<button
		onclick={onClose}
		class="shrink-0 text-gray-400 hover:text-white transition-colors p-1 rounded hover:bg-gray-800"
		aria-label="닫기"
	>
		<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" viewBox="0 0 20 20" fill="currentColor">
			<path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
		</svg>
	</button>
</div>
