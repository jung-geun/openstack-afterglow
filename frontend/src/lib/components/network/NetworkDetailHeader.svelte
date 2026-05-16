<script lang="ts">
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import { useNetworkDetail } from '$lib/stores/networkDetail.svelte';

	interface Props {
		onClose?: () => void;
		ar: { active: boolean; intervalSeconds: number; intervalOptions: number[] };
	}

	let { onClose, ar }: Props = $props();
	const s = useNetworkDetail();
</script>

<div class="flex items-center justify-between px-5 py-4 border-b border-gray-800 flex-shrink-0">
	<h2 class="text-sm font-semibold text-white truncate">{s.network?.name || ''}</h2>
	<div class="flex items-center gap-2 ml-3 flex-shrink-0">
		<AutoRefreshControl
			bind:active={ar.active}
			bind:intervalSeconds={ar.intervalSeconds}
			intervalOptions={ar.intervalOptions}
			refreshing={s.loading}
			onManualRefresh={() => s.fetchNetwork()}
		/>
		<button onclick={onClose} class="text-gray-400 hover:text-white text-xl leading-none">×</button>
	</div>
</div>
