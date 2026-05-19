<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import type { ImageInfo } from '$lib/types/compute';

	let {
		target,
		onClose,
		onSaved,
	}: {
		target: ImageInfo | null;
		onClose: () => void;
		onSaved: (updated: ImageInfo) => void;
	} = $props();

	let form = $state({ name: '', os_distro: '', os_type: '', min_disk: 0, min_ram: 0 });
	let saving = $state(false);
	let saveError = $state('');

	$effect(() => {
		if (target) {
			form = {
				name: target.name,
				os_distro: target.os_distro ?? '',
				os_type: '',
				min_disk: target.min_disk ?? 0,
				min_ram: target.min_ram ?? 0,
			};
			saveError = '';
		}
	});

	async function save() {
		if (!target) return;
		saving = true;
		saveError = '';
		try {
			const body: Record<string, unknown> = {};
			if (form.name !== target.name) body.name = form.name;
			if (form.os_distro !== (target.os_distro ?? '')) body.os_distro = form.os_distro || null;
			if (form.os_type) body.os_type = form.os_type;
			if (form.min_disk !== target.min_disk) body.min_disk = form.min_disk;
			if (form.min_ram !== target.min_ram) body.min_ram = form.min_ram;
			if (Object.keys(body).length === 0) { onClose(); return; }
			const updated = await api.patch<ImageInfo>(
				`/api/images/${target.id}`, body,
				$auth.token ?? undefined, $auth.projectId ?? undefined,
			);
			onSaved(updated);
			onClose();
		} catch (e) {
			saveError = e instanceof ApiError ? e.message : '저장 실패';
		} finally {
			saving = false;
		}
	}
</script>

{#if target}
	<div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
	     onclick={() => { onClose(); }}
	     role="dialog" aria-modal="true" tabindex="-1"
	     onkeydown={(e) => e.key === 'Escape' && onClose()}>
		<div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl"
		     onclick={(e) => e.stopPropagation()}
		     role="none" onkeydown={(e) => e.stopPropagation()}>
			<h2 class="text-lg font-semibold text-white mb-5">이미지 메타데이터 편집</h2>
			<div class="space-y-4">
				<div>
					<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름
						<input bind:value={form.name} type="text" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
					</label>
				</div>
				<div>
					<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">OS Distro
						<input bind:value={form.os_distro} type="text" placeholder="ubuntu, centos, rocky..." class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
					</label>
				</div>
				<div class="grid grid-cols-2 gap-3">
					<div>
						<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">최소 디스크 (GB)
							<input bind:value={form.min_disk} type="number" min="0" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
						</label>
					</div>
					<div>
						<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">최소 RAM (MB)
							<input bind:value={form.min_ram} type="number" min="0" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
						</label>
					</div>
				</div>
			</div>
			{#if saveError}<div class="mt-3 text-red-400 text-xs">{saveError}</div>{/if}
			<div class="flex justify-end gap-3 mt-6">
				<button onclick={() => { onClose(); }} class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">취소</button>
				<button onclick={save} disabled={saving} class="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors">{saving ? '저장 중...' : '저장'}</button>
			</div>
		</div>
	</div>
{/if}
