<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';

	interface AdminVolume {
		id: string;
		name: string;
		status: string;
		size: number;
		project_id: string | null;
		created_at: string | null;
		bootable?: boolean;
	}

	let {
		volume,
		onClose,
		onSuccess,
	}: {
		volume: AdminVolume | null;
		onClose: () => void;
		onSuccess: () => void;
	} = $props();

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	let newSize = $state(0);
	let extending = $state(false);
	let extendError = $state('');

	$effect(() => {
		if (volume) {
			newSize = volume.size + 10;
			extendError = '';
		}
	});

	async function confirmExtend() {
		if (!volume) return;
		extending = true;
		extendError = '';
		try {
			await api.post(`/api/v1/admin/volumes/${volume.id}/extend`, { new_size: newSize }, token, projectId);
			onSuccess();
			onClose();
		} catch (e) {
			extendError = e instanceof ApiError ? e.message : '확장 실패';
		} finally {
			extending = false;
		}
	}
</script>

{#if volume}
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
		onclick={onClose}
		role="dialog" aria-modal="true" tabindex="-1"
		onkeydown={(e) => e.key === 'Escape' && onClose()}
	>
		<div
			class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-sm mx-4 shadow-2xl"
			onclick={(e) => e.stopPropagation()}
			role="none"
			onkeydown={(e) => e.stopPropagation()}
		>
			<h2 class="text-lg font-semibold text-white mb-3">용량 확장</h2>
			<p class="text-xs text-gray-500 mb-4">현재: {volume.size} GB</p>
			{#if extendError}
				<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{extendError}</div>
			{/if}
			<div>
				<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">새 크기 (GB)</label>
				<input bind:value={newSize} type="number" min={volume.size + 1} class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
			</div>
			<div class="flex justify-end gap-3 mt-5">
				<button onclick={onClose} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">취소</button>
				<button onclick={confirmExtend} disabled={extending || newSize <= volume.size} class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg disabled:opacity-30">{extending ? '확장 중...' : '확장'}</button>
			</div>
		</div>
	</div>
{/if}
