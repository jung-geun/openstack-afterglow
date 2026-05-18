<script lang="ts">
	import type { RouterDetail } from '$lib/types/router';
	import type { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';

	let {
		router,
		saving,
		ar,
		onManualRefresh,
		onDelete,
		onBack,
	}: {
		router: RouterDetail;
		saving: boolean;
		ar: ReturnType<typeof createAutoRefresh>;
		onManualRefresh: () => void;
		onDelete: () => Promise<void>;
		onBack: () => void;
	} = $props();
</script>

<button onclick={onBack} class="text-sm text-gray-400 hover:text-gray-200 mb-6 inline-flex items-center gap-1">
	← 라우터 목록
</button>

<div class="flex items-start justify-between mb-8">
	<div>
		<h1 class="text-2xl font-bold text-white">{router.name || router.id.slice(0, 12)}</h1>
		<div class="flex items-center gap-3 mt-2">
			<span class="px-2 py-0.5 rounded text-xs font-medium {router.status === 'ACTIVE' ? 'text-green-400 bg-green-900/30' : 'text-gray-400 bg-gray-800'}">
				{router.status}
			</span>
			<span class="text-xs text-gray-500 font-mono">{router.id}</span>
		</div>
	</div>
	<div class="flex items-center gap-2">
		<AutoRefreshControl
			bind:active={ar.active}
			bind:intervalSeconds={ar.intervalSeconds}
			intervalOptions={ar.intervalOptions}
			refreshing={saving}
			onManualRefresh={onManualRefresh}
		/>
		<button
			onclick={onDelete}
			disabled={saving}
			class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors"
		>삭제</button>
	</div>
</div>
