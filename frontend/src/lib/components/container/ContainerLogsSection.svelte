<script lang="ts">
	import { useContainerDetailController } from '$lib/stores/containerDetailController.svelte';

	const s = useContainerDetailController();
</script>

<div class="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
	<button
		onclick={s.toggleLogs}
		class="w-full flex items-center justify-between px-4 py-3 text-xs text-gray-400 hover:text-white transition-colors"
	>
		<span class="uppercase tracking-wide font-medium">로그</span>
		<span class="text-gray-600">{s.logsOpen ? '▲' : '▼'}</span>
	</button>
	{#if s.logsOpen}
		<div class="px-4 pb-4">
			<div class="flex justify-end mb-2">
				<button onclick={s.fetchLogs} disabled={s.logsLoading} class="text-xs text-blue-400 hover:text-blue-300 disabled:opacity-40">
					{s.logsLoading ? '조회 중...' : '새로고침'}
				</button>
			</div>
			{#if s.logs}
				<pre class="bg-gray-950 rounded p-3 text-xs text-gray-300 overflow-auto max-h-64 font-mono whitespace-pre-wrap">{s.logs}</pre>
			{:else}
				<div class="text-gray-600 text-xs">새로고침을 클릭하세요</div>
			{/if}
		</div>
	{/if}
</div>
