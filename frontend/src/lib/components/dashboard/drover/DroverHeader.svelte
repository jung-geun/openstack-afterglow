<script lang="ts">
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import TutorialStartButton from '$lib/tutorial/TutorialStartButton.svelte';
	import type { AutoRefreshController } from '$lib/utils/autoRefresh.svelte';

	let {
		showDeleted = $bindable(),
		ar,
		refreshing,
		onForceRefresh,
		onOpenCreate,
		onToggleDeleted,
	}: {
		showDeleted: boolean;
		ar: AutoRefreshController;
		refreshing: boolean;
		onForceRefresh: () => void;
		onOpenCreate: () => void;
		onToggleDeleted: () => void;
	} = $props();
</script>

<PageHeader breadcrumb="CONTAINERS / K3S" title="Drover 클러스터">
	{#snippet actions()}
		<TutorialStartButton tour="drover" />
		<button
			onclick={onToggleDeleted}
			class="hidden sm:inline-flex text-xs px-3 py-1.5 rounded border transition-colors {showDeleted
				? 'border-gray-500 text-gray-300 bg-gray-800'
				: 'border-gray-700 text-gray-500 hover:border-gray-500 hover:text-gray-400'}"
		>
			{showDeleted ? '삭제 이력 숨기기' : '삭제 이력 보기'}
		</button>
		<AutoRefreshControl
			bind:active={ar.active}
			bind:intervalSeconds={ar.intervalSeconds}
			intervalOptions={ar.intervalOptions}
			{refreshing}
			onManualRefresh={onForceRefresh}
		/>
		<button
			data-tour="drover-create-open"
			onclick={onOpenCreate}
			class="bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
		>
			+ 클러스터 생성
		</button>
	{/snippet}
</PageHeader>
