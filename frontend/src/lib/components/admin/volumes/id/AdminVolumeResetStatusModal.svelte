<script lang="ts">
	let {
		open = $bindable(),
		resetting,
		onReset,
	}: {
		open: boolean;
		resetting: boolean;
		onReset: (status: string) => Promise<boolean>;
	} = $props();

	let resetStatus = $state('available');

	$effect(() => {
		if (!open) {
			resetStatus = 'available';
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
			<h2 class="text-lg font-semibold text-white mb-4">상태 초기화</h2>
			<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">변경할 상태</label>
			<select bind:value={resetStatus} class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mb-4">
				<option value="available">available</option>
				<option value="error">error</option>
				<option value="in-use">in-use</option>
			</select>
			<div class="flex gap-3 justify-end">
				<button onclick={() => { open = false; }} class="px-4 py-2 text-sm text-gray-400 hover:text-white">취소</button>
				<button
					onclick={async () => {
						const ok = await onReset(resetStatus);
						if (ok) open = false;
					}}
					disabled={resetting}
					class="px-4 py-2 bg-yellow-600 hover:bg-yellow-500 text-white text-sm rounded-lg disabled:opacity-30"
				>
					{resetting ? '처리 중...' : '초기화'}
				</button>
			</div>
		</div>
	</div>
{/if}
