<script lang="ts">
	import { useObjectBrowser } from '$lib/stores/objectBrowser.svelte';
	const s = useObjectBrowser();
</script>

{#if s.selectedCount > 0}
	<div class="flex items-center gap-3 mb-3 px-3 py-2 bg-indigo-950/40 border border-indigo-800/50 rounded-lg">
		<span class="text-xs text-indigo-300">{s.selectedCount}개 선택됨</span>
		<div class="flex-1"></div>
		<button
			onclick={() => { s.selected = new Set(); }}
			class="text-xs text-gray-400 hover:text-white transition-colors"
		>선택 해제</button>
		<button
			onclick={s.openBulkMove}
			class="text-xs text-white bg-indigo-700 hover:bg-indigo-600 transition-colors px-3 py-1.5 rounded border border-indigo-600"
		>선택 이동</button>
		<button
			onclick={s.bulkDelete}
			disabled={s.bulkDeleting}
			class="text-xs text-white bg-red-700 hover:bg-red-600 disabled:bg-gray-700 disabled:text-gray-500 transition-colors px-3 py-1.5 rounded border border-red-600 disabled:border-gray-600"
		>{s.bulkDeleting ? '삭제 중...' : '선택 삭제'}</button>
	</div>
{/if}
