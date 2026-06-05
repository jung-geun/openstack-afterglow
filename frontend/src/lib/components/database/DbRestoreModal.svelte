<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import type { DbFlavor, DbBackup } from '$lib/types/database';

	interface Props {
		open: boolean;
		backup: DbBackup | null;
		flavors?: DbFlavor[];
		onRestore: (backupId: string, name: string, flavorId: string, volumeSize: number) => Promise<void>;
		onClose: () => void;
	}

	let { open = $bindable(), backup, flavors: externalFlavors, onRestore, onClose }: Props = $props();

	let name = $state('');
	let flavorId = $state('');
	let volumeSize = $state(5);
	let loadedFlavors = $state<DbFlavor[]>([]);
	let submitting = $state(false);
	let error = $state('');

	const flavors = $derived(externalFlavors && externalFlavors.length > 0 ? externalFlavors : loadedFlavors);
	const minVolume = $derived(backup?.size ? Math.max(5, Math.ceil(backup.size)) : 5);

	$effect(() => {
		if (!open || !backup) return;
		name = backup.name ? `${backup.name}-restored` : 'restored-db';
		volumeSize = minVolume;
		error = '';
		if (!externalFlavors || externalFlavors.length === 0) {
			api.get<DbFlavor[]>('/api/database-instances/flavors', $auth.token ?? undefined, $auth.projectId ?? undefined)
				.then(f => {
					loadedFlavors = f;
					if (f.length > 0 && !flavorId) flavorId = String(f[0].id);
				})
				.catch(() => {});
		} else if (externalFlavors.length > 0 && !flavorId) {
			flavorId = String(externalFlavors[0].id);
		}
	});

	async function handleSubmit() {
		if (!backup || !name.trim() || !flavorId) { error = '모든 항목을 입력하세요.'; return; }
		if (volumeSize < minVolume) { error = `볼륨 크기는 ${minVolume}GB 이상이어야 합니다.`; return; }
		submitting = true; error = '';
		try {
			await onRestore(backup.id, name.trim(), flavorId, volumeSize);
			open = false;
		} catch (e) {
			error = e instanceof ApiError ? e.message : '복원 실패';
		} finally {
			submitting = false;
		}
	}

	function handleClose() {
		open = false;
		onClose();
	}
</script>

{#if open && backup}
	<div
		class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
		onclick={handleClose}
		onkeydown={(e) => e.key === 'Escape' && handleClose()}
		role="dialog"
		aria-modal="true"
		tabindex="-1"
	>
		<div
			class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl"
			onclick={(e) => e.stopPropagation()}
			role="none"
			onkeydown={(e) => e.stopPropagation()}
		>
			<h2 class="text-lg font-semibold text-white mb-1">백업에서 복원</h2>
			<p class="text-xs text-gray-500 mb-4">백업 <span class="text-gray-300 font-medium">"{backup.name || backup.id.slice(0, 8)}"</span> 에서 새 DB 인스턴스를 생성합니다.</p>

			<div class="space-y-3">
				<label class="flex flex-col gap-1">
					<span class="text-xs text-gray-500">새 인스턴스 이름 <span class="text-red-400">*</span></span>
					<input
						type="text"
						bind:value={name}
						placeholder="복원 인스턴스 이름"
						class="bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-blue-500"
					/>
				</label>

				<label class="flex flex-col gap-1">
					<span class="text-xs text-gray-500">Flavor <span class="text-red-400">*</span></span>
					<select
						bind:value={flavorId}
						class="bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
					>
						{#if flavors.length === 0}
							<option value="">로드 중...</option>
						{:else}
							{#each flavors as f}
								<option value={String(f.id)}>{f.name} ({f.vcpus}vCPU / {f.ram}MB)</option>
							{/each}
						{/if}
					</select>
				</label>

				<label class="flex flex-col gap-1">
					<span class="text-xs text-gray-500">볼륨 크기 (GB) <span class="text-xs text-gray-600">최소 {minVolume}GB</span></span>
					<input
						type="number"
						bind:value={volumeSize}
						min={minVolume}
						step="1"
						class="bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-blue-500"
					/>
				</label>
			</div>

			{#if error}
				<p class="text-red-400 text-xs mt-3">{error}</p>
			{/if}

			<div class="flex justify-end gap-3 mt-5">
				<button
					onclick={handleClose}
					class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors"
				>
					취소
				</button>
				<button
					onclick={handleSubmit}
					disabled={submitting}
					class="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors"
				>
					{submitting ? '복원 중...' : '복원 시작'}
				</button>
			</div>
		</div>
	</div>
{/if}
