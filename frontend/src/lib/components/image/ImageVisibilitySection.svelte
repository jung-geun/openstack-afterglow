<script lang="ts">
	import { useImageDetail, VISIBILITY_OPTIONS } from '$lib/stores/imageDetail.svelte';
	import Button from '$lib/components/ui/Button.svelte';

	const s = useImageDetail();
</script>

<div class="bg-gray-900 border border-gray-800 rounded-lg p-5">
	<h3 class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">공개 범위 수정</h3>
	<div class="flex items-center gap-3 flex-wrap">
		<select
			bind:value={s.visibilityValue}
			class="bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
		>
			{#each VISIBILITY_OPTIONS as opt}
				<option value={opt.value}>{opt.label}</option>
			{/each}
		</select>
		<Button onclick={() => s.saveVisibility()} disabled={s.savingVisibility || s.visibilityValue === s.image!.visibility}>
			{s.savingVisibility ? '저장 중...' : '저장'}
		</Button>
		{#if s.visibilitySuccess}
			<span class="text-green-400 text-sm">저장됨</span>
		{/if}
		{#if s.visibilityError}
			<span class="text-red-400 text-sm">{s.visibilityError}</span>
		{/if}
	</div>
</div>
