<script lang="ts">
	interface Props {
		open: boolean;
		creating: boolean;
		error: string;
		onCreate: (name: string, description: string) => Promise<boolean>;
	}

	let { open = $bindable(), creating, error, onCreate }: Props = $props();

	let form = $state({ name: '', description: '' });

	async function handleCreate() {
		const ok = await onCreate(form.name, form.description);
		if (ok) {
			form = { name: '', description: '' };
			open = false;
		}
	}
</script>

{#if open}
	<div
		class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
		onclick={() => { open = false; }}
		role="dialog"
		onkeydown={(e) => e.key === 'Escape' && (open = false)}
		tabindex="-1"
	>
		<div
			class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl"
			onclick={(e) => e.stopPropagation()}
		>
			<h2 class="text-lg font-semibold text-white mb-5">그룹 생성</h2>
			{#if error}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>{/if}
			<div class="space-y-4">
				<div>
					<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름</label>
					<input bind:value={form.name} type="text" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
				</div>
				<div>
					<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">설명</label>
					<input bind:value={form.description} type="text" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
				</div>
			</div>
			<div class="flex justify-end gap-3 mt-6">
				<button onclick={() => { open = false; }} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">취소</button>
				<button onclick={handleCreate} disabled={creating || !form.name} class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg disabled:opacity-30">{creating ? '생성 중...' : '생성'}</button>
			</div>
		</div>
	</div>
{/if}
