<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import { apiMut } from '$lib/api/mutations';

	let {
		open = $bindable(false),
		onCreated,
	}: {
		open: boolean;
		onCreated: () => void;
	} = $props();

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	let form = $state({ name: '', size_gb: 10 });
	let creating = $state(false);
	let createError = $state('');

	async function createVolume() {
		if (!form.name.trim() || form.size_gb < 1) return;
		creating = true;
		createError = '';
		try {
			await apiMut('볼륨 생성', () => api.post('/api/v1/volumes', form, token, projectId));
			open = false;
			form = { name: '', size_gb: 10 };
			onCreated();
		} catch (e) {
			createError = e instanceof ApiError ? e.message : '생성 실패';
		} finally {
			creating = false;
		}
	}

	function close() {
		open = false;
		createError = '';
	}
</script>

{#if open}
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
		onclick={close}
		role="dialog" aria-modal="true" tabindex="-1"
		onkeydown={(e) => e.key === 'Escape' && close()}
	>
		<div
			class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl"
			onclick={(e) => e.stopPropagation()}
			role="none"
			onkeydown={(e) => e.stopPropagation()}
		>
			<h2 class="text-lg font-semibold text-white mb-5">볼륨 생성</h2>
			<div class="space-y-4">
				<div>
					<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름
						<input bind:value={form.name} type="text" placeholder="my-volume" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
					</label>
				</div>
				<div>
					<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">크기 (GB)
						<input bind:value={form.size_gb} type="number" min="1" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
					</label>
				</div>
			</div>
			{#if createError}
				<div class="mt-4 text-red-400 text-xs bg-red-900/20 border border-red-800 rounded px-3 py-2">{createError}</div>
			{/if}
			<div class="flex justify-end gap-3 mt-6">
				<button onclick={close} class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">취소</button>
				<button
					onclick={createVolume}
					disabled={creating || !form.name.trim() || form.size_gb < 1}
					class="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors"
				>{creating ? '생성 중...' : '생성'}</button>
			</div>
		</div>
	</div>
{/if}
