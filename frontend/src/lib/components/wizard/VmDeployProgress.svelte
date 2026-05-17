<script lang="ts">
	import { useVmCreate } from '$lib/stores/vmCreateStore.svelte';
	import ProgressBar from '$lib/components/ProgressBar.svelte';

	const s = useVmCreate();
</script>

<div class="mb-6">
	<h1 class="text-xl font-bold text-white">VM 생성</h1>
	<p class="text-sm text-gray-500 mt-1">배포 진행 중</p>
</div>

<div class="bg-gray-900 rounded-xl border border-gray-700 p-6 mb-6">
	<h2 class="text-lg font-semibold text-white mb-4">VM 배포 진행 중</h2>
	<ProgressBar
		steps={s.progressSteps}
		currentStep={s.currentStep}
		progress={s.progress}
		error={s.deployError}
	/>
	<div class="flex items-center justify-between mt-4">
		<p class="text-gray-400 text-sm">{s.progressMessage}</p>
		{#if s.elapsedSeconds !== null}
			<p class="text-gray-600 text-xs font-mono">{s.elapsedSeconds.toFixed(0)}s 경과</p>
		{/if}
	</div>
</div>
