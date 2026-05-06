<script lang="ts">
	import { uploadQueue } from '$lib/stores/uploadQueue';

	interface Props {
		containerName: string;
		prefix?: string;
		token?: string;
		projectId?: string;
		onSuccess: () => void;
		onClose: () => void;
	}

	const { containerName, prefix = '', token, projectId, onSuccess, onClose }: Props = $props();

	let files = $state<FileList | null>(null);
	let error = $state('');

	function enqueue() {
		if (!files || files.length === 0) return;
		for (const file of Array.from(files)) {
			uploadQueue.enqueue(file, {
				containerName,
				prefix,
				token,
				projectId,
				onComplete: (job) => {
					if (job.status === 'success') onSuccess();
				}
			});
		}
		onClose();
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') onClose();
	}
</script>

<div
	class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
	onclick={onClose}
	role="dialog"
	aria-modal="true"
	tabindex="-1"
	onkeydown={handleKeydown}
>
	<div
		class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl"
		onclick={(e) => e.stopPropagation()}
		role="none"
		onkeydown={(e) => e.stopPropagation()}
	>
		<h2 class="text-lg font-semibold text-white mb-4">파일 업로드</h2>

		<div class="space-y-3">
			<input
				type="file"
				multiple
				onchange={(e) => {
					files = (e.target as HTMLInputElement).files;
					error = '';
				}}
				class="w-full text-sm text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:bg-gray-700 file:text-white hover:file:bg-gray-600"
			/>
			{#if error}
				<p class="text-red-400 text-xs">{error}</p>
			{/if}
		</div>

		<div class="flex justify-end gap-2 mt-5">
			<button
				onclick={onClose}
				class="px-4 py-2 text-sm text-gray-400 hover:text-white border border-gray-700 rounded-lg transition-colors"
			>취소</button>
			<button
				onclick={enqueue}
				disabled={!files || files.length === 0}
				class="px-4 py-2 text-sm bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded-lg transition-colors"
			>업로드</button>
		</div>
	</div>
</div>
