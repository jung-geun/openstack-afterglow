<script lang="ts">
	let {
		open = $bindable(),
		creating,
		error,
		onCreate,
	}: {
		open: boolean;
		creating: boolean;
		error: string;
		onCreate: (form: { name: string; description: string }) => Promise<boolean>;
	} = $props();

	let form = $state({ name: '', description: '' });

	async function handleCreate() {
		const ok = await onCreate(form);
		if (ok) {
			form = { name: '', description: '' };
		}
	}
</script>

{#if open}
	<div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
		onclick={() => { open = false; }}
		onkeydown={(e) => e.key === 'Escape' && (open = false)}
		role="dialog" aria-modal="true" tabindex="-1">
		<div class="bg-gray-800 border border-gray-700 rounded-xl p-6 w-full max-w-sm mx-4" onclick={(e) => e.stopPropagation()} role="none" onkeydown={(e) => e.stopPropagation()}>
			<h3 class="text-lg font-semibold text-white mb-4">보안 그룹 생성</h3>
			<div class="space-y-3 mb-4">
				<div>
					<label class="block text-xs text-gray-400 mb-1">이름 *
						<input bind:value={form.name} placeholder="보안 그룹 이름"
							class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 placeholder-gray-500 focus:border-blue-500 focus:outline-none mt-1" />
					</label>
				</div>
				<div>
					<label class="block text-xs text-gray-400 mb-1">설명
						<input bind:value={form.description} placeholder="설명 (선택)"
							class="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm text-gray-200 placeholder-gray-500 focus:border-blue-500 focus:outline-none mt-1" />
					</label>
				</div>
			</div>
			{#if error}
				<p class="text-xs text-red-400 mb-3">{error}</p>
			{/if}
			<div class="flex gap-2">
				<button onclick={handleCreate} disabled={creating || !form.name.trim()}
					class="flex-1 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm py-2 rounded transition-colors">
					{creating ? '생성 중...' : '생성'}
				</button>
				<button onclick={() => { open = false; }}
					class="flex-1 bg-gray-700 hover:bg-gray-600 text-gray-300 text-sm py-2 rounded transition-colors">취소</button>
			</div>
		</div>
	</div>
{/if}
