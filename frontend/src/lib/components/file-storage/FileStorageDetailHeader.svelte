<script lang="ts">
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import { useFileStorageDetailController } from '$lib/stores/fileStorageDetailController.svelte';

	interface Props {
		onClose?: () => void;
		ar: { active: boolean; intervalSeconds: number; intervalOptions: number[] };
	}

	let { onClose, ar }: Props = $props();
	const s = useFileStorageDetailController();
</script>

<div class="flex items-center justify-between mb-4">
	<button onclick={onClose} class="text-gray-400 hover:text-gray-200 text-sm transition-colors">← 목록으로</button>
	<AutoRefreshControl
		bind:active={ar.active}
		bind:intervalSeconds={ar.intervalSeconds}
		intervalOptions={ar.intervalOptions}
		refreshing={s.loading}
		onManualRefresh={() => s.fetchAll()}
	/>
</div>
