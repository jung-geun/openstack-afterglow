<script lang="ts">
	import type { Group } from '$lib/types/adminGroup';

	interface Props {
		target: Group | null;
		deleting: boolean;
		error: string;
		onConfirm: () => Promise<void>;
	}

	let { target = $bindable(), deleting, error, onConfirm }: Props = $props();
</script>

{#if target}
	<div
		class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
		onclick={() => { target = null; }}
		role="dialog"
		onkeydown={(e) => e.key === 'Escape' && (target = null)}
		tabindex="-1"
	>
		<div
			class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-sm mx-4 shadow-2xl"
			onclick={(e) => e.stopPropagation()}
		>
			<h2 class="text-lg font-semibold text-white mb-3">그룹 삭제</h2>
			<p class="text-sm text-gray-400 mb-4"><span class="text-white font-medium">{target.name}</span> 그룹을 삭제하시겠습니까?</p>
			{#if error}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>{/if}
			<div class="flex justify-end gap-3">
				<button onclick={() => { target = null; }} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">취소</button>
				<button onclick={onConfirm} disabled={deleting} class="px-4 py-2 bg-red-600 hover:bg-red-500 text-white text-sm font-medium rounded-lg disabled:opacity-30">{deleting ? '삭제 중...' : '삭제'}</button>
			</div>
		</div>
	</div>
{/if}
