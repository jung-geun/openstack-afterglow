<script lang="ts">
	import { formatNumber } from '$lib/utils/format';

	let {
		open = $bindable(),
		currentSize,
		extending,
		onExtend,
	}: {
		open: boolean;
		currentSize: number;
		extending: boolean;
		onExtend: (newSize: number) => Promise<boolean>;
	} = $props();

	let newSize = $state(currentSize + 10);

	$effect(() => {
		if (open) {
			newSize = currentSize + 10;
		}
	});
</script>

{#if open}
	<div
		class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
		onclick={() => { open = false; }}
		role="dialog"
		onkeydown={(e) => e.key === 'Escape' && (open = false)}
		tabindex="-1"
	>
		<div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-sm mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()}>
			<h2 class="text-lg font-semibold text-white mb-4">볼륨 확장</h2>
			<p class="text-sm text-gray-400 mb-4">현재 크기: {formatNumber(currentSize)} GB</p>
			<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">새 크기 (GB)</label>
			<input bind:value={newSize} type="number" min={currentSize + 1} class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mb-4" />
			<div class="flex gap-3 justify-end">
				<button onclick={() => { open = false; }} class="px-4 py-2 text-sm text-gray-400 hover:text-white">취소</button>
				<button
					onclick={async () => {
						const ok = await onExtend(newSize);
						if (ok) open = false;
					}}
					disabled={extending}
					class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg disabled:opacity-30"
				>
					{extending ? '확장 중...' : '확장'}
				</button>
			</div>
		</div>
	</div>
{/if}
