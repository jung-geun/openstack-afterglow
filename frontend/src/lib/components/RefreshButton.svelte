<script lang="ts">
	let { refreshing = false, onclick }: { refreshing?: boolean; onclick: () => void } = $props();
</script>

<button
	{onclick}
	disabled={refreshing}
	class="text-xs text-gray-400 hover:text-white transition-colors px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600 disabled:opacity-50 flex items-center gap-1.5"
>
	{#if refreshing}
		<svg class="w-3.5 h-3.5 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
			<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
		</svg>
	{/if}
	새로고침
</button>
