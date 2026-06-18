<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';

	let { onClose, onSuccess }: {
		onClose: () => void;
		onSuccess: (project: { id: string; name: string }) => void;
	} = $props();

	let name = $state('');
	let description = $state('');
	let submitting = $state(false);
	let error = $state('');

	async function submit() {
		if (!name.trim() || submitting) return;
		submitting = true;
		error = '';
		try {
			const result = await api.post<{ id: string; name: string; description: string }>(
				'/api/v1/projects',
				{ name: name.trim(), description: description.trim() },
				$auth.token ?? undefined
			);
			onSuccess(result);
		} catch (e) {
			error = e instanceof ApiError ? e.message : '프로젝트 생성 실패';
		} finally {
			submitting = false;
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') onClose();
		if (e.key === 'Enter' && name.trim()) submit();
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<div
	class="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
	onclick={onClose}
	role="dialog"
	aria-modal="true"
	aria-label="새 프로젝트 생성"
>
	<div
		class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md shadow-2xl"
		onclick={(e) => e.stopPropagation()}
		role="none"
	>
		<h2 class="text-base font-semibold text-white mb-4">새 프로젝트 생성</h2>

		<div class="space-y-3">
			<div>
				<label class="block text-xs text-gray-400 mb-1.5" for="proj-name">
					프로젝트 이름 <span class="text-red-400">*</span>
				</label>
				<input
					id="proj-name"
					bind:value={name}
					placeholder="my-project"
					class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-blue-500 transition-colors"
					autofocus
				/>
			</div>
			<div>
				<label class="block text-xs text-gray-400 mb-1.5" for="proj-desc">설명 (선택)</label>
				<input
					id="proj-desc"
					bind:value={description}
					placeholder="프로젝트 설명"
					class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-blue-500 transition-colors"
				/>
			</div>
		</div>

		{#if error}
			<div class="mt-3 text-xs text-red-400">{error}</div>
		{/if}

		<div class="flex justify-end gap-2 mt-5">
			<button
				onclick={onClose}
				class="px-3 py-2 text-sm text-gray-400 hover:text-white transition-colors"
			>
				취소
			</button>
			<button
				onclick={submit}
				disabled={!name.trim() || submitting}
				class="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-600/40 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors"
			>
				{submitting ? '생성 중...' : '생성'}
			</button>
		</div>
	</div>
</div>
