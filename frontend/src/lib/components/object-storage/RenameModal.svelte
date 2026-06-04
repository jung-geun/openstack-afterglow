<script lang="ts">
	import { useObjectBrowser } from '$lib/stores/objectBrowser.svelte';
	const s = useObjectBrowser();
</script>

{#if s.showRename}
	<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/70">
		<div class="bg-gray-900 border border-gray-800 rounded-xl p-6 w-full max-w-sm shadow-2xl">
			<h2 class="text-white font-semibold mb-1">이름 변경</h2>
			<p class="text-gray-500 text-xs mb-4 break-all">{s.displayName(s.renameTarget)}</p>
			{#if s.renameError}<p class="text-red-400 text-xs mb-2">{s.renameError}</p>{/if}
			<input
				type="text"
				bind:value={s.renameNew}
				placeholder="새 이름"
				class="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm mb-4 focus:outline-none focus:border-indigo-500"
				onkeydown={(e) => e.key === 'Enter' && s.doRename()}
			/>
			<div class="flex gap-2 justify-end">
				<button
					onclick={() => { s.showRename = false; }}
					class="text-xs text-gray-400 hover:text-white px-3 py-1.5 rounded border border-gray-700"
				>취소</button>
				<button
					onclick={s.doRename}
					disabled={s.renaming}
					class="text-xs text-white bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-700 px-3 py-1.5 rounded border border-indigo-500 disabled:border-gray-600"
				>{s.renaming ? '변경 중...' : '변경'}</button>
			</div>
		</div>
	</div>
{/if}
