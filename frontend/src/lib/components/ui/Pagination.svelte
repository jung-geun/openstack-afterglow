<script lang="ts">
	let {
		page,
		totalPages = null,
		hasPrev,
		hasNext,
		onPrev,
		onNext,
		total = null,
		pageSize = null,
		note = null,
	}: {
		page: number;
		totalPages?: number | null;
		hasPrev: boolean;
		hasNext: boolean;
		onPrev: () => void;
		onNext: () => void;
		total?: number | null;
		pageSize?: number | null;
		note?: string | null;
	} = $props();
</script>

<div class="flex items-center justify-between mt-3 text-xs text-gray-500">
	<button
		disabled={!hasPrev}
		onclick={onPrev}
		class="px-3 py-1.5 rounded bg-gray-800 hover:bg-gray-700 text-gray-300 disabled:opacity-30 disabled:cursor-not-allowed"
	>← 이전</button>
	<div class="flex items-center gap-2">
		{#if total != null && pageSize != null}
			<span>{total}개 중 {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)}개{note ? ' ' + note : ''}</span>
		{:else if note}
			<span>{note}</span>
		{/if}
		<span class="text-gray-400 font-medium">{totalPages != null ? `${page} / ${totalPages}` : `페이지 ${page}`}</span>
	</div>
	<button
		disabled={!hasNext}
		onclick={onNext}
		class="px-3 py-1.5 rounded bg-gray-800 hover:bg-gray-700 text-gray-300 disabled:opacity-30 disabled:cursor-not-allowed"
	>다음 →</button>
</div>
