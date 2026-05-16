<script lang="ts">
	import { useAdminVolumeDetail } from '$lib/stores/adminVolumeDetail.svelte';

	interface Props {
		onClose?: () => void;
	}

	let { onClose }: Props = $props();

	const s = useAdminVolumeDetail();
</script>

<div class="flex items-center justify-between px-5 py-4 border-b border-gray-800 flex-shrink-0">
	<h2 class="text-sm font-semibold text-white truncate">{s.volume?.name || 'Volume'}</h2>
	<button onclick={onClose} class="text-gray-400 hover:text-white text-xl leading-none ml-3 flex-shrink-0">×</button>
</div>
