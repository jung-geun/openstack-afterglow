<script lang="ts">
	let { step, totalSteps, stepName, adminMode = false, adminProjectName = null, onReset, onClose }: {
		step: number;
		totalSteps: number;
		stepName: string;
		adminMode?: boolean;
		adminProjectName?: string | null;
		onReset: () => void;
		onClose: () => void;
	} = $props();
</script>

<div class="flex items-start justify-between mb-6">
	<div>
		<h1 class="text-2xl font-bold text-white tracking-tight leading-tight">
			VM 생성
			{#if adminMode}
				<span class="text-sm font-normal text-amber-400 ml-2">관리자 · {adminProjectName ?? ''}</span>
			{/if}
		</h1>
		<div class="text-[12.5px] text-gray-500 font-mono uppercase tracking-[0.06em] mt-1.5">
			STEP <b class="text-warm font-semibold">{step}</b> / {totalSteps} · <b class="text-warm font-semibold">{stepName}</b>
		</div>
	</div>
	<div class="flex items-center gap-3.5 mt-0.5">
		<button
			onclick={onReset}
			class="text-xs text-gray-500 hover:text-gray-300 transition-colors"
		>↺ 새로 시작</button>
		<button
			onclick={onClose}
			class="w-8 h-8 rounded-lg flex items-center justify-center text-gray-500 hover:text-white hover:bg-gray-800 transition-all"
			aria-label="닫기"
		>
			<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18 6L6 18M6 6l12 12"/>
			</svg>
		</button>
	</div>
</div>

<style>
  .text-warm {
    color: var(--color-warm);
  }
</style>
