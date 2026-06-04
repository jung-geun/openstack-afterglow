<script lang="ts">
	import { useObjectBrowser } from '$lib/stores/objectBrowser.svelte';
	const s = useObjectBrowser();
</script>

{#if s.dragActive}
	<div class="fixed inset-0 z-50 pointer-events-none flex items-center justify-center bg-indigo-950/40 backdrop-blur-sm border-4 border-dashed border-indigo-500">
		<div class="text-center">
			<svg class="w-16 h-16 mx-auto text-indigo-300 mb-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12"/></svg>
			<p class="text-indigo-100 font-semibold text-xl">{s.containerName}{s.prefix ? ` / ${s.prefix}` : ''} 에 업로드</p>
			<p class="text-indigo-300 text-sm mt-1">파일을 여기에 떨어뜨리세요</p>
		</div>
	</div>
{/if}
