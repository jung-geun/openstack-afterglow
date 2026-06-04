<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';

	let {
		open = $bindable(false),
		onCreated,
	}: {
		open: boolean;
		onCreated: () => void;
	} = $props();

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	let form = $state({ name: '', description: '', enabled: true });
	let creating = $state(false);
	let createError = $state('');

	$effect(() => {
		if (open) {
			form = { name: '', description: '', enabled: true };
			createError = '';
		}
	});

	async function createProject() {
		creating = true;
		createError = '';
		try {
			await api.post(
				'/api/admin/projects',
				{ name: form.name, description: form.description || null, enabled: form.enabled },
				token,
				projectId,
			);
			open = false;
			onCreated();
		} catch (e) {
			createError = e instanceof ApiError ? e.message : '생성 실패';
		} finally {
			creating = false;
		}
	}
</script>

{#if open}
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
		onclick={() => { open = false; createError = ''; }}
		role="dialog" aria-modal="true" tabindex="-1"
		onkeydown={(e) => e.key === 'Escape' && (open = false)}
	>
		<div
			class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl"
			onclick={(e) => e.stopPropagation()}
			role="none"
			onkeydown={(e) => e.stopPropagation()}
		>
			<h2 class="text-lg font-semibold text-white mb-5">프로젝트 생성</h2>
			{#if createError}
				<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{createError}</div>
			{/if}
			<div class="space-y-4">
				<div>
					<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름</label>
					<input bind:value={form.name} type="text" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
				</div>
				<div>
					<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">설명</label>
					<input bind:value={form.description} type="text" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
				</div>
				<div class="flex items-center gap-3">
					<button
						onclick={() => (form.enabled = !form.enabled)}
						class="relative w-11 h-6 rounded-full transition-colors {form.enabled ? 'bg-blue-600' : 'bg-gray-700'}"
					><span class="absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform {form.enabled ? 'translate-x-5' : ''}"></span></button>
					<span class="text-sm text-gray-300">{form.enabled ? '활성' : '비활성'}</span>
				</div>
			</div>
			<div class="flex justify-end gap-3 mt-6">
				<button onclick={() => { open = false; createError = ''; }} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">취소</button>
				<button onclick={createProject} disabled={creating || !form.name} class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg disabled:opacity-30">{creating ? '생성 중...' : '생성'}</button>
			</div>
		</div>
	</div>
{/if}
