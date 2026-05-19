<script lang="ts">
	import { dialogState } from '$lib/stores/confirm.svelte';
</script>

{#if dialogState.open}
	<div
		class="fixed inset-0 z-[200] flex items-center justify-center bg-black/60"
		role="dialog"
		aria-modal="true"
	>
		<div class="bg-gray-900 border border-gray-700 rounded-xl shadow-2xl p-6 w-full max-w-sm mx-4">
			<p class="text-gray-200 text-sm whitespace-pre-wrap mb-6">{dialogState.message}</p>
			<div class="flex gap-3 justify-end">
				<button
					onclick={dialogState.reject}
					class="px-4 py-2 text-sm text-gray-300 hover:text-white border border-gray-600 hover:border-gray-400 rounded-lg transition-colors"
				>
					취소
				</button>
				<button
					onclick={dialogState.accept}
					class="px-4 py-2 text-sm text-white bg-red-600 hover:bg-red-500 rounded-lg transition-colors"
				>
					확인
				</button>
			</div>
		</div>
	</div>
{/if}

<svelte:window onkeydown={(e) => { if (e.key === 'Escape' && dialogState.open) dialogState.reject(); }} />
