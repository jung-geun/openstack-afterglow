<script lang="ts">
	import { uploadQueue } from '$lib/stores/uploadQueue';

	interface Props {
		open: boolean;
		token?: string;
		projectId?: string;
		initialFile?: File | null;
		onUploaded?: () => void;
		onClose?: () => void;
	}

	let { open = $bindable(), token, projectId, initialFile = null, onUploaded, onClose }: Props = $props();

	const DISK_FORMATS = ['raw', 'qcow2', 'vmdk', 'vdi', 'vhd', 'vhdx', 'iso', 'ami'] as const;

	let name = $state('');
	let diskFormat = $state<string>('raw');
	let visibility = $state('private');
	let osDistro = $state('');
	let file = $state<File | null>(null);
	let dropActive = $state(false);
	let formError = $state('');

	$effect(() => {
		if (initialFile) {
			file = initialFile;
			if (!name) name = initialFile.name.replace(/\.[^.]+$/, '');
		}
	});

	$effect(() => {
		if (!open) {
			name = '';
			diskFormat = 'raw';
			visibility = 'private';
			osDistro = '';
			file = null;
			dropActive = false;
			formError = '';
		}
	});

	function close() {
		open = false;
		onClose?.();
	}

	function onFileInput(e: Event) {
		const input = e.currentTarget as HTMLInputElement;
		const f = input.files?.[0];
		if (f) {
			file = f;
			if (!name) name = f.name.replace(/\.[^.]+$/, '');
		}
	}

	function onDropzoneEnter(e: DragEvent) {
		if (!hasFiles(e)) return;
		e.preventDefault();
		dropActive = true;
	}
	function onDropzoneOver(e: DragEvent) {
		if (!hasFiles(e)) return;
		e.preventDefault();
		dropActive = true;
	}
	function onDropzoneLeave() {
		dropActive = false;
	}
	function onDropzoneDrop(e: DragEvent) {
		e.preventDefault();
		dropActive = false;
		const f = e.dataTransfer?.files?.[0];
		if (f) {
			file = f;
			if (!name) name = f.name.replace(/\.[^.]+$/, '');
		}
	}

	function hasFiles(e: DragEvent): boolean {
		const types = e.dataTransfer?.types;
		if (!types) return false;
		for (let i = 0; i < types.length; i++) if (types[i] === 'Files') return true;
		return false;
	}

	function submit() {
		formError = '';
		if (!name.trim()) { formError = '이미지 이름을 입력하세요.'; return; }
		if (!file) { formError = '업로드할 파일을 선택하세요.'; return; }

		const extraFields: Record<string, string> = {
			name: name.trim(),
			disk_format: diskFormat,
			visibility,
		};
		if (osDistro.trim()) extraFields.os_distro = osDistro.trim();

		uploadQueue.enqueue(file, {
			endpoint: '/api/images',
			extraFields,
			kind: 'image',
			token,
			projectId,
			onComplete: (job) => {
				if (job.status === 'success') onUploaded?.();
			},
		});
		close();
	}

	function formatBytes(n: number): string {
		if (n >= 1073741824) return `${(n / 1073741824).toFixed(1)} GB`;
		if (n >= 1048576) return `${(n / 1048576).toFixed(1)} MB`;
		if (n >= 1024) return `${(n / 1024).toFixed(0)} KB`;
		return `${n} B`;
	}
</script>

{#if open}
	<div
		class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
		onclick={close}
		role="dialog"
		aria-modal="true"
		tabindex="-1"
		onkeydown={(e) => e.key === 'Escape' && close()}
	>
		<div
			class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-lg mx-4 shadow-2xl"
			onclick={(e) => e.stopPropagation()}
			role="none"
			onkeydown={(e) => e.stopPropagation()}
		>
			<h2 class="text-lg font-semibold text-white mb-5">이미지 업로드</h2>

			<!-- 드롭존 -->
			<div
				class="border-2 border-dashed rounded-xl p-6 mb-5 text-center transition-colors cursor-pointer
					{dropActive ? 'border-blue-500 bg-blue-900/10' : 'border-gray-700 hover:border-gray-600'}"
				role="button"
				tabindex="0"
				ondragenter={onDropzoneEnter}
				ondragover={onDropzoneOver}
				ondragleave={onDropzoneLeave}
				ondrop={onDropzoneDrop}
				onclick={() => (document.getElementById('image-file-input') as HTMLInputElement)?.click()}
				onkeydown={(e) => e.key === 'Enter' && (document.getElementById('image-file-input') as HTMLInputElement)?.click()}
			>
				{#if file}
					<div class="text-sm text-white font-medium">{file.name}</div>
					<div class="text-xs text-gray-500 mt-1">{formatBytes(file.size)}</div>
					<button
						class="text-xs text-gray-500 hover:text-red-400 mt-2 transition-colors"
						onclick={(e) => { e.stopPropagation(); file = null; }}
					>파일 제거</button>
				{:else}
					<div class="text-gray-500 text-sm">파일을 드래그하거나 클릭해서 선택</div>
					<div class="text-gray-600 text-xs mt-1">raw, qcow2, vmdk, iso 등</div>
				{/if}
			</div>
			<input id="image-file-input" type="file" class="hidden" onchange={onFileInput} />

			<div class="space-y-4">
				<!-- 이름 -->
				<div>
					<label for="img-name" class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">
						이미지 이름 <span class="text-red-400">*</span>
					</label>
					<input
						id="img-name"
						bind:value={name}
						type="text"
						placeholder="my-custom-image"
						class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
					/>
				</div>

				<div class="grid grid-cols-2 gap-3">
					<!-- Disk Format -->
					<div>
						<label for="img-disk-format" class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">Disk Format</label>
						<select
							id="img-disk-format"
							bind:value={diskFormat}
							class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
						>
							{#each DISK_FORMATS as fmt}
								<option value={fmt}>{fmt}</option>
							{/each}
						</select>
					</div>

					<!-- Visibility -->
					<div>
						<label for="img-visibility" class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">가시성</label>
						<select
							id="img-visibility"
							bind:value={visibility}
							class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
						>
							<option value="private">비공개</option>
							<option value="shared">공유</option>
						</select>
					</div>
				</div>

				<!-- OS Distro -->
				<div>
					<label for="img-os-distro" class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">OS Distro (선택)</label>
					<input
						id="img-os-distro"
						bind:value={osDistro}
						type="text"
						placeholder="ubuntu, centos, windows..."
						class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
					/>
				</div>
			</div>

			{#if formError}
				<div class="mt-3 text-red-400 text-xs">{formError}</div>
			{/if}

			<div class="flex justify-end gap-3 mt-6">
				<button
					onclick={close}
					class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors"
				>취소</button>
				<button
					onclick={submit}
					class="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-colors"
				>업로드 시작</button>
			</div>
		</div>
	</div>
{/if}
