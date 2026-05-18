<script lang="ts">
	let {
		currentPage = $bindable(),
		totalPages,
		total,
		pageSize,
	}: {
		currentPage: number;
		totalPages: number;
		total: number;
		pageSize: number;
	} = $props();
</script>

<div class="flex items-center justify-between mt-4 text-xs text-gray-500">
	<span>{total}개 중 {currentPage * pageSize + 1}–{Math.min((currentPage + 1) * pageSize, total)}개</span>
	<div class="flex gap-2">
		<button
			onclick={() => { currentPage--; }}
			disabled={currentPage === 0}
			class="px-3 py-1 rounded border border-gray-700 hover:border-gray-600 disabled:opacity-30 disabled:cursor-not-allowed"
		>이전</button>
		<span class="px-3 py-1 text-gray-400">{currentPage + 1} / {totalPages}</span>
		<button
			onclick={() => { currentPage++; }}
			disabled={currentPage >= totalPages - 1}
			class="px-3 py-1 rounded border border-gray-700 hover:border-gray-600 disabled:opacity-30 disabled:cursor-not-allowed"
		>다음</button>
	</div>
</div>
