<script lang="ts">
	import type { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import GradientText from '$lib/components/ui/GradientText.svelte';

	let {
		username,
		projectName,
		ar,
		refreshing,
		onForceRefresh,
	}: {
		username: string;
		projectName: string;
		ar: ReturnType<typeof createAutoRefresh>;
		refreshing: boolean;
		onForceRefresh: () => void;
	} = $props();
</script>

<div class="flex items-start justify-between">
	<div>
		<div class="text-[11px] text-gray-500 uppercase tracking-widest font-medium mb-1">OVERVIEW · 대시보드</div>
		<h1 class="text-2xl font-bold text-white mb-1">안녕하세요, <GradientText>{username}</GradientText>님</h1>
		<div class="text-gray-400 text-[13px]">
			{projectName} · 최근 동기화 방금 전
		</div>
	</div>
	<AutoRefreshControl
		bind:active={ar.active}
		bind:intervalSeconds={ar.intervalSeconds}
		intervalOptions={ar.intervalOptions}
		{refreshing}
		onManualRefresh={onForceRefresh}
	/>
</div>
