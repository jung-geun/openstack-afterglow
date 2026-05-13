<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import type { Volume } from '$lib/types/resources';

	let { volume, onclose, onsuccess }: {
		volume: Volume | null;
		onclose: () => void;
		onsuccess: () => void;
	} = $props();

	let newSize = $state(0);
	let extending = $state(false);
	let error = $state('');

	$effect(() => {
		if (volume) {
			newSize = volume.size + 10;
			error = '';
		}
	});

	async function confirmExtend() {
		if (!volume) return;
		if (newSize <= volume.size) {
			error = `새 크기(${newSize}GB)는 현재 크기(${volume.size}GB)보다 커야 합니다`;
			return;
		}
		extending = true;
		error = '';
		try {
			await api.post(
				`/api/volumes/${volume.id}/extend`,
				{ new_size: newSize },
				$auth.token ?? undefined,
				$auth.projectId ?? undefined,
			);
			onsuccess();
		} catch (e) {
			error = e instanceof ApiError ? e.message : '볼륨 확장 실패';
		} finally {
			extending = false;
		}
	}
</script>

{#if volume}
<div
	class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
	onclick={onclose}
	role="dialog"
	aria-modal="true"
	tabindex="-1"
	onkeydown={(e) => e.key === 'Escape' && onclose()}
>
	<div
		class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl"
		onclick={(e) => e.stopPropagation()}
		role="none"
		onkeydown={(e) => e.stopPropagation()}
	>
		<h2 class="text-lg font-semibold text-white mb-5">볼륨 용량 확장</h2>
		<div class="space-y-4">
			<div>
				<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">볼륨</label>
				<div class="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-300 text-sm">
					{volume.name || volume.id.slice(0, 8)} <span class="text-gray-500">({volume.status})</span>
				</div>
			</div>
			<div>
				<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">현재 크기</label>
				<div class="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-400 text-sm font-mono">
					{volume.size} GB
				</div>
			</div>
			<div>
				<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">
					새 크기 (GB) — 최소 {volume.size + 1}GB
					<input
						bind:value={newSize}
						type="number"
						min={volume.size + 1}
						step="10"
						class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm font-mono focus:outline-none focus:border-blue-500 mt-1.5"
					/>
				</label>
			</div>
		</div>
		{#if error}<div class="mt-4 text-red-400 text-xs bg-red-900/20 border border-red-800 rounded px-3 py-2">{error}</div>{/if}
		<div class="flex justify-end gap-3 mt-6">
			<button onclick={onclose} class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">취소</button>
			<button
				onclick={confirmExtend}
				disabled={extending || newSize <= volume.size}
				class="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors"
			>{extending ? '확장 중...' : '확장'}</button>
		</div>
	</div>
</div>
{/if}
