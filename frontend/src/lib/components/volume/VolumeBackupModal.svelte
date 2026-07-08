<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import type { Volume } from '$lib/types/volume';

	let { volume, onclose, onsuccess }: {
		volume: Volume | null;
		onclose: () => void;
		onsuccess: () => void;
	} = $props();

	let name = $state('');
	let description = $state('');
	let incremental = $state(false);
	let creating = $state(false);
	let error = $state('');

	function defaultName(vol: Volume): string {
		const now = new Date();
		const pad = (n: number) => String(n).padStart(2, '0');
		const ts = `${now.getFullYear()}${pad(now.getMonth()+1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}`;
		return `${vol.name || vol.id.slice(0, 8)}-backup-${ts}`;
	}

	$effect(() => {
		if (volume) {
			name = defaultName(volume);
			description = '';
			incremental = false;
			error = '';
		}
	});

	async function createBackup() {
		if (!volume) return;
		creating = true;
		error = '';
		try {
			await api.post(
				'/api/v1/volumes/backups',
				{ volume_id: volume.id, name, description: description || null, incremental },
				$auth.token ?? undefined,
				$auth.projectId ?? undefined,
			);
			onsuccess();
		} catch (e) {
			error = e instanceof ApiError ? e.message : '백업 생성 실패';
		} finally {
			creating = false;
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
		<h2 class="text-lg font-semibold text-white mb-5">볼륨 백업 생성</h2>
		<div class="space-y-4">
			<div>
				<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">볼륨</label>
				<div class="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-300 text-sm">
					{volume.name || volume.id.slice(0, 8)} <span class="text-gray-500">({volume.size} GB)</span>
				</div>
			</div>
			<div>
				<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">백업 이름
					<input
						bind:value={name}
						type="text"
						placeholder="my-backup"
						class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5"
					/>
				</label>
			</div>
			<div>
				<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">설명 (선택)
					<input
						bind:value={description}
						type="text"
						class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5"
					/>
				</label>
			</div>
			<div class="flex items-center gap-2">
				<input type="checkbox" id="backup-incremental" bind:checked={incremental} class="rounded border-gray-600" />
				<label for="backup-incremental" class="text-sm text-gray-300">증분 백업</label>
			</div>
		</div>
		{#if error}<div class="mt-4 text-red-400 text-xs bg-red-900/20 border border-red-800 rounded px-3 py-2">{error}</div>{/if}
		<div class="flex justify-end gap-3 mt-6">
			<button onclick={onclose} class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">취소</button>
			<button
				onclick={createBackup}
				disabled={creating || !name.trim()}
				class="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors"
			>{creating ? '생성 중...' : '백업 생성'}</button>
		</div>
	</div>
</div>
{/if}
