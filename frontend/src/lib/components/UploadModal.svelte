<script lang="ts">
	import { api, ApiError } from '$lib/api/client';

	interface Props {
		containerName: string;
		token?: string;
		projectId?: string;
		onSuccess: () => void;
		onClose: () => void;
	}

	const { containerName, token, projectId, onSuccess, onClose }: Props = $props();

	let file = $state<File | null>(null);
	let uploading = $state(false);
	let error = $state('');
	let progress = $state(0);      // 0–100
	let loaded = $state(0);        // 전송된 바이트
	let total = $state(0);         // 전체 바이트
	let startTime = $state(0);     // 업로드 시작 시각 (Date.now())
	let now = $state(0);           // 경과 시간 갱신용
	let abortFn = $state<(() => void) | null>(null);
	let intervalId: ReturnType<typeof setInterval> | null = null;

	const elapsed = $derived(uploading && startTime > 0 ? (now - startTime) / 1000 : 0);
	const speed = $derived(elapsed > 0 ? loaded / elapsed : 0); // bytes/sec
	const remaining = $derived(speed > 0 && total > loaded ? (total - loaded) / speed : 0); // seconds

	function formatBytes(n: number): string {
		if (n >= 1073741824) return `${(n / 1073741824).toFixed(1)} GB`;
		if (n >= 1048576) return `${(n / 1048576).toFixed(1)} MB`;
		if (n >= 1024) return `${(n / 1024).toFixed(0)} KB`;
		return `${n} B`;
	}

	function formatTime(sec: number): string {
		if (!isFinite(sec) || sec <= 0) return '--';
		const s = Math.ceil(sec);
		if (s < 60) return `${s}초`;
		const m = Math.floor(s / 60);
		const r = s % 60;
		return r > 0 ? `${m}분 ${r}초` : `${m}분`;
	}

	function formatSpeed(bps: number): string {
		if (!bps || !isFinite(bps)) return '--';
		return `${formatBytes(bps)}/s`;
	}

	function reset() {
		file = null;
		uploading = false;
		error = '';
		progress = 0;
		loaded = 0;
		total = 0;
		startTime = 0;
		now = 0;
		abortFn = null;
		if (intervalId !== null) { clearInterval(intervalId); intervalId = null; }
	}

	async function upload() {
		if (!file) return;
		uploading = true;
		error = '';
		progress = 0;
		loaded = 0;
		total = file.size;
		startTime = Date.now();
		now = startTime;

		intervalId = setInterval(() => { now = Date.now(); }, 500);

		const formData = new FormData();
		formData.append('file', file);

		const { promise, abort } = api.uploadWithProgress(
			`/api/object-storage/${encodeURIComponent(containerName)}/objects`,
			formData,
			(e) => {
				loaded = e.loaded;
				total = e.total;
				progress = total > 0 ? Math.round((e.loaded / e.total) * 100) : 0;
			},
			token,
			projectId,
		);
		abortFn = abort;

		try {
			await promise;
			if (intervalId !== null) { clearInterval(intervalId); intervalId = null; }
			onSuccess();
			onClose();
		} catch (e) {
			if (intervalId !== null) { clearInterval(intervalId); intervalId = null; }
			if (e instanceof ApiError && e.status === 0) {
				// 취소된 경우
				reset();
				return;
			}
			error = e instanceof ApiError ? e.message : (e instanceof Error ? e.message : '업로드 실패');
			uploading = false;
			abortFn = null;
		}
	}

	function cancel() {
		abortFn?.();
		reset();
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape' && !uploading) onClose();
	}
</script>

<div
	class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
	onclick={() => { if (!uploading) onClose(); }}
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

		{#if uploading}
			<!-- 업로드 진행 중 -->
			<div class="space-y-3">
				<!-- 파일 정보 -->
				<div class="flex items-center justify-between text-sm">
					<span class="text-gray-300 truncate max-w-[260px]">{file?.name}</span>
					<span class="text-gray-500 shrink-0 ml-2">{formatBytes(total)}</span>
				</div>

				<!-- 진행률 바 -->
				<div class="bg-gray-800 rounded-full h-2 overflow-hidden">
					<div
						class="bg-indigo-500 h-2 rounded-full transition-all duration-300"
						style="width: {progress}%"
					></div>
				</div>

				<!-- % + 전송량 -->
				<div class="flex items-center justify-between text-xs text-gray-400">
					<span class="font-mono">{progress}%</span>
					<span>{formatBytes(loaded)} / {formatBytes(total)}</span>
				</div>

				<!-- 시간/속도 정보 -->
				<div class="grid grid-cols-3 gap-2 pt-1">
					<div class="bg-gray-800/60 rounded-lg px-3 py-2 text-center">
						<div class="text-gray-500 text-xs mb-0.5">경과</div>
						<div class="text-white text-xs font-mono">{formatTime(elapsed)}</div>
					</div>
					<div class="bg-gray-800/60 rounded-lg px-3 py-2 text-center">
						<div class="text-gray-500 text-xs mb-0.5">남은 시간</div>
						<div class="text-white text-xs font-mono">{formatTime(remaining)}</div>
					</div>
					<div class="bg-gray-800/60 rounded-lg px-3 py-2 text-center">
						<div class="text-gray-500 text-xs mb-0.5">속도</div>
						<div class="text-white text-xs font-mono">{formatSpeed(speed)}</div>
					</div>
				</div>

				{#if error}
					<p class="text-red-400 text-xs">{error}</p>
				{/if}
			</div>

			<div class="flex justify-end mt-5">
				<button
					onclick={cancel}
					class="px-4 py-2 text-sm text-gray-400 hover:text-white border border-gray-700 hover:border-gray-500 rounded-lg transition-colors"
				>취소</button>
			</div>
		{:else}
			<!-- 파일 선택 -->
			<div class="space-y-3">
				<input
					type="file"
					onchange={(e) => { file = (e.target as HTMLInputElement).files?.[0] ?? null; error = ''; }}
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
					onclick={upload}
					disabled={!file}
					class="px-4 py-2 text-sm bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded-lg transition-colors"
				>업로드</button>
			</div>
		{/if}
	</div>
</div>
