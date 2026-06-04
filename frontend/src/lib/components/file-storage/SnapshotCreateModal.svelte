<script lang="ts">
	import type { FileStorage } from '$lib/types/fileStorage';

	let {
		open = $bindable(),
		fileStorages,
		onCreate,
	}: {
		open: boolean;
		fileStorages: FileStorage[];
		onCreate: (form: { share_id: string; name: string; description: string }) => Promise<string | true>;
	} = $props();

	let form = $state({ share_id: '', name: '', description: '' });
	let creating = $state(false);
	let error = $state('');

	$effect(() => {
		if (!open) {
			form = { share_id: '', name: '', description: '' };
			error = '';
			creating = false;
		} else if (fileStorages.length > 0 && !form.share_id) {
			form.share_id = fileStorages[0].id;
		}
	});

	async function submit() {
		if (!form.share_id || !form.name.trim()) return;
		creating = true;
		error = '';
		const result = await onCreate({ ...form });
		creating = false;
		if (result === true) {
			open = false;
		} else {
			error = result;
		}
	}
</script>

{#if open}
	<div
		class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
		onclick={() => (open = false)}
		role="dialog"
		aria-modal="true"
		tabindex="-1"
		onkeydown={(e) => e.key === 'Escape' && (open = false)}
	>
		<div
			class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-lg mx-4 shadow-2xl"
			onclick={(e) => e.stopPropagation()}
			role="none"
			onkeydown={(e) => e.stopPropagation()}
		>
			<h2 class="text-lg font-semibold text-white mb-5">스냅샷 생성</h2>
			{#if fileStorages.length === 0}
				<p class="text-sm text-gray-400 mb-4">파일 스토리지가 없습니다.</p>
			{:else}
				<div class="space-y-4">
					<div>
						<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">파일 스토리지 *
							<select bind:value={form.share_id} class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5">
								<option value="">파일 스토리지 선택</option>
								{#each fileStorages as fs}
									<option value={fs.id}>{fs.name || fs.id.slice(0, 12)} ({fs.size} GB)</option>
								{/each}
							</select>
						</label>
					</div>
					<div>
						<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">스냅샷 이름 *
							<input bind:value={form.name} type="text" placeholder="snapshot-name" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
						</label>
					</div>
					<div>
						<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">설명 (선택)
							<input bind:value={form.description} type="text" placeholder="설명" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
						</label>
					</div>
				</div>
			{/if}
			{#if error}
				<div class="mt-4 text-red-400 text-xs bg-red-900/20 border border-red-800 rounded px-3 py-2">{error}</div>
			{/if}
			<div class="flex justify-end gap-3 mt-6">
				<button onclick={() => (open = false)} class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">취소</button>
				<button
					onclick={submit}
					disabled={creating || !form.share_id || !form.name.trim()}
					class="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors"
				>{creating ? '생성 중...' : '생성'}</button>
			</div>
		</div>
	</div>
{/if}
