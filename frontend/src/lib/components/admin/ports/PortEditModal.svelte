<script lang="ts">
	import type { PortInfo } from '$lib/types/resources';

	let {
		target = $bindable(),
		updating,
		error,
		onSave,
	}: {
		target: PortInfo | null;
		updating: boolean;
		error: string;
		onSave: (name: string) => Promise<boolean>;
	} = $props();

	let name = $state('');

	// Sync name from target whenever a new port is opened for editing
	$effect(() => {
		if (target) name = target.name ?? '';
	});

	async function handleSave() {
		const success = await onSave(name);
		if (success) name = '';
	}
</script>

{#if target}
	<div
		class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
		onclick={() => { target = null; }}
		role="dialog"
		onkeydown={(e) => e.key === 'Escape' && (target = null)}
		tabindex="-1"
	>
		<div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()}>
			<h2 class="text-lg font-semibold text-white mb-5">포트 수정</h2>
			{#if error}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>{/if}
			<div>
				<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름</label>
				<input bind:value={name} type="text" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
			</div>
			<div class="flex justify-end gap-3 mt-6">
				<button onclick={() => { target = null; }} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">취소</button>
				<button onclick={handleSave} disabled={updating} class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg disabled:opacity-30">{updating ? '수정 중...' : '수정'}</button>
			</div>
		</div>
	</div>
{/if}
