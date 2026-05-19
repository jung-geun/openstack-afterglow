<script lang="ts">
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import { goto } from '$app/navigation';
	import { useRouterDetailController } from '$lib/stores/routerDetailController.svelte';

	interface Props {
		onClose?: () => void;
		routerId: string;
		ar: { active: boolean; intervalSeconds: number; intervalOptions: number[] };
	}

	let { onClose, routerId, ar }: Props = $props();
	const s = useRouterDetailController();
</script>

<div class="flex items-center justify-between mb-6 border-b border-gray-800 pb-4">
	<h2 class="text-xl font-bold text-white">라우터 상세</h2>
	<div class="flex items-center gap-2">
		<AutoRefreshControl
			bind:active={ar.active}
			bind:intervalSeconds={ar.intervalSeconds}
			intervalOptions={ar.intervalOptions}
			refreshing={s.loading}
			onManualRefresh={() => s.fetchRouter()}
		/>
		<button
			onclick={() => goto(`/dashboard/network/routers/${routerId}`)}
			class="text-xs text-gray-400 hover:text-blue-300 px-2 py-1 rounded border border-gray-700 hover:border-blue-700 transition-colors"
		>전체 보기 →</button>
		{#if onClose}
			<button onclick={onClose} class="text-gray-400 hover:text-white text-xl leading-none px-2">✕</button>
		{/if}
	</div>
</div>
