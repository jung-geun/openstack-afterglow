<script lang="ts">
	import { useInstanceDetailController } from '$lib/stores/instanceDetailController.svelte';

	interface Props {
		onClose: () => void;
		preselectFlavorId?: string;
	}

	let { onClose, preselectFlavorId = '' }: Props = $props();

	const s = useInstanceDetailController();

	let resizeFlavorId = $state(preselectFlavorId);

	async function handleResize() {
		const ok = await s.doResize(resizeFlavorId);
		if (ok) onClose();
	}
</script>

<div
	class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
	role="dialog"
	onclick={onClose}
	onkeydown={(e) => e.key === 'Escape' && onClose()}
	tabindex="-1"
>
	<div
		class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl"
		onclick={(e) => e.stopPropagation()}
	>
		<h2 class="text-lg font-semibold text-white mb-1">인스턴스 리사이즈</h2>
		<p class="text-xs text-gray-500 mb-5">플레이버를 변경합니다. 완료 후 '리사이즈 확인' 또는 '되돌리기'를 선택하세요.</p>
		{#if s.resizeError}
			<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{s.resizeError}</div>
		{/if}
		<div class="space-y-4">
			<div>
				<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">새 플레이버</label>
				<select bind:value={resizeFlavorId} class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-violet-500">
					<option value="">플레이버 선택</option>
					{#each s.resizeFlavors as f}
						<option value={f.id}>{f.name} ({f.vcpus} vCPU / {f.ram >= 1024 ? (f.ram / 1024).toFixed(0) + ' GB' : f.ram + ' MB'} RAM)</option>
					{/each}
				</select>
			</div>
		</div>
		<div class="flex justify-end gap-3 mt-6">
			<button onclick={onClose} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">취소</button>
			<button
				onclick={handleResize}
				disabled={s.resizeLoading || !resizeFlavorId}
				class="px-4 py-2 bg-violet-700 hover:bg-violet-600 text-white text-sm font-medium rounded-lg disabled:opacity-30"
			>
				{s.resizeLoading ? '리사이즈 중...' : '리사이즈'}
			</button>
		</div>
	</div>
</div>
