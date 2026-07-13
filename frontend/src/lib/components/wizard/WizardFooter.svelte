<script lang="ts">
	import Button from '$lib/components/ui/Button.svelte';

	let { imageDisplay, flavorDisplay, libCount, step, totalSteps, canPrev, canNext,
		onCancel, onPrev, onNext, onDeploy }: {
		imageDisplay?: string | null;
		flavorDisplay?: string | null;
		libCount?: number;
		step: number;
		totalSteps: number;
		canPrev: boolean;
		canNext: boolean;
		onCancel: () => void;
		onPrev: () => void;
		onNext: () => void;
		onDeploy: () => void;
	} = $props();

	const isLast = $derived(step === totalSteps);
</script>

<div class="flex items-center justify-between flex-wrap gap-3 pt-4 border-t border-gray-800">
	<!-- selection chips strip -->
	<div class="flex flex-wrap items-center gap-2 text-xs text-gray-500 min-w-0">
		{#if imageDisplay}
			<span class="pick">이미지: <b class="text-gray-300 font-mono font-medium">{imageDisplay}</b></span>
		{/if}
		{#if flavorDisplay}
			<span class="pick">플레이버: <b class="text-gray-300 font-mono font-medium">{flavorDisplay}</b></span>
		{/if}
		{#if libCount && libCount > 0}
			<span class="pick">라이브러리: <b class="text-gray-300 font-mono font-medium">{libCount}개</b></span>
		{/if}
	</div>

	<!-- nav buttons -->
	<div class="flex items-center gap-2 ml-auto flex-shrink-0" data-tour="wizard-nav">
		<button
			onclick={onCancel}
			class="px-4 py-2 text-sm text-gray-400 hover:text-red-400 border border-gray-700 hover:border-red-900/60 hover:bg-red-950/20 rounded-lg transition-all"
		>취소</button>
		{#if canPrev}
			<button
				onclick={onPrev}
				class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors flex items-center gap-1"
			>← 이전</button>
		{/if}
		{#if !isLast}
			<Button onclick={onNext} disabled={!canNext}>다음 →</Button>
		{:else}
			<Button onclick={onDeploy} disabled={!canNext}>VM 생성</Button>
		{/if}
	</div>
</div>

<style>
  .pick {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 10px;
    border-radius: 6px;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgb(55 65 81 / 0.8);
  }
</style>
