<script lang="ts">
	import type { AdminRouter } from '$lib/types/resources';

	let {
		router = $bindable(),
		onUpdate,
	}: {
		router: AdminRouter | null;
		onUpdate: (id: string, form: { name: string }) => Promise<string | true>;
	} = $props();

	let name = $state('');
	let updating = $state(false);
	let error = $state('');

	$effect(() => {
		if (router) {
			name = router.name;
			error = '';
			updating = false;
		}
	});

	async function submit() {
		if (!router) return;
		updating = true;
		error = '';
		const result = await onUpdate(router.id, { name });
		updating = false;
		if (result === true) router = null;
		else error = result;
	}
</script>

{#if router}
	<div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onclick={() => { router = null; }} role="dialog" onkeydown={(e) => e.key === 'Escape' && (router = null)} tabindex="-1">
		<div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()} role="none" onkeydown={(e) => e.stopPropagation()}>
			<h2 class="text-lg font-semibold text-white mb-5">라우터 수정</h2>
			{#if error}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>{/if}
			<div>
				<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름</label>
				<input bind:value={name} type="text" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
			</div>
			<div class="flex justify-end gap-3 mt-6">
				<button onclick={() => { router = null; }} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">취소</button>
				<button onclick={submit} disabled={updating} class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg disabled:opacity-30">{updating ? '수정 중...' : '수정'}</button>
			</div>
		</div>
	</div>
{/if}
