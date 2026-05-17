<script lang="ts">
	import type { AdminImage } from '$lib/types/adminImage';

	let {
		target = $bindable(),
		form = $bindable(),
		editing,
		editError,
		onSave,
	}: {
		target: AdminImage | null;
		form: { name: string; os_distro: string; visibility: string };
		editing: boolean;
		editError: string;
		onSave: () => Promise<void>;
	} = $props();
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
			class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl"
			onclick={(e) => e.stopPropagation()}
		>
			<h2 class="text-lg font-semibold text-white mb-5">이미지 수정</h2>
			{#if editError}
				<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{editError}</div>
			{/if}
			<div class="space-y-4">
				<div>
					<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름</label>
					<input
						bind:value={form.name}
						type="text"
						class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
					/>
				</div>
				<div>
					<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">OS 배포판</label>
					<input
						bind:value={form.os_distro}
						type="text"
						placeholder="ubuntu, centos, rocky ..."
						class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
					/>
				</div>
				<div>
					<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">공개 범위</label>
					<select
						bind:value={form.visibility}
						class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
					>
						<option value="public">public</option>
						<option value="community">community</option>
						<option value="shared">shared</option>
						<option value="private">private</option>
					</select>
				</div>
			</div>
			<div class="flex justify-end gap-3 mt-6">
				<button onclick={() => { target = null; }} class="px-4 py-2 text-sm text-gray-400 hover:text-white">취소</button>
				<button
					onclick={onSave}
					disabled={editing}
					class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg disabled:opacity-30"
				>
					{editing ? '저장 중...' : '저장'}
				</button>
			</div>
		</div>
	</div>
{/if}
