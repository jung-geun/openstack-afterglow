<script lang="ts">
	let { cur, totalSteps, stepLabels, goTo }: {
		cur: number;
		totalSteps: number;
		stepLabels: string[];
		goTo: (n: number) => void;
	} = $props();

	const progressPct = $derived(((cur - 1) / Math.max(1, totalSteps - 1)) * 100);
</script>

<div class="relative bg-gray-900 border border-gray-800 rounded-2xl px-6 py-4 mb-6">
	<!-- progress track (background) + fill (자식으로 좌표계 통일) -->
	<div class="absolute left-6 right-6 top-1/2 h-[2px] bg-gray-800 rounded-full -translate-y-1/2 overflow-hidden">
		<div class="h-full progress-fill rounded-full" style="width: {progressPct}%"></div>
	</div>

	<!-- step dots + labels -->
	<div class="relative flex justify-between">
		{#each stepLabels as label, i}
			{@const step = i + 1}
			{@const isDone = cur > step}
			{@const isCurrent = cur === step}

			<button
				type="button"
				onclick={() => { if (isDone) goTo(step); }}
				class="flex items-center gap-2 bg-gray-900 px-1.5 {isDone ? 'cursor-pointer' : 'cursor-default'}"
				tabindex={isDone ? 0 : -1}
				aria-current={isCurrent ? 'step' : undefined}
			>
				{#if isDone}
					<div class="step-dot-done w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 transition-transform hover:scale-105">
						<svg class="w-3.5 h-3.5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"/>
						</svg>
					</div>
				{:else if isCurrent}
					<div class="step-dot-current w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 text-sm font-bold text-white">
						{step}
					</div>
				{:else}
					<div class="w-7 h-7 rounded-full bg-gray-800 border border-gray-700 flex items-center justify-center flex-shrink-0 text-xs font-medium text-gray-500">
						{step}
					</div>
				{/if}
				<span class="text-xs hidden sm:inline font-medium {isCurrent ? 'text-white' : isDone ? 'text-gray-400 group-hover:text-white' : 'text-gray-600'}">{label}</span>
			</button>
		{/each}
	</div>
</div>

<style>
  .progress-fill {
    background: var(--gradient-warm);
    transition: width 0.4s cubic-bezier(0.2, 0.7, 0.2, 1);
  }
  .step-dot-done {
    background: var(--gradient-warm);
  }
  .step-dot-current {
    background: var(--gradient-warm);
    box-shadow: 0 0 12px color-mix(in oklab, var(--color-warm) 40%, transparent);
  }
</style>
