<script lang="ts">
	import Modal from '$lib/components/ui/Modal.svelte';
	import StatusChip from '$lib/components/ui/StatusChip.svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import type { LibraryBuildDetail } from '$lib/types/libraries';

	let {
		buildId,
		open = $bindable(false),
		onCancelled,
	}: {
		buildId: number | null;
		open: boolean;
		onCancelled?: () => void;
	} = $props();

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	let detail = $state<LibraryBuildDetail | null>(null);
	let loading = $state(false);
	let cancelling = $state(false);
	let cancelError = $state('');

	const TERMINAL = new Set(['complete', 'error', 'timeout', 'cancelled']);
	const isActive = $derived(detail ? !TERMINAL.has(detail.status) : false);

	async function loadDetail() {
		if (!buildId) return;
		loading = true;
		try {
			detail = await api.get<LibraryBuildDetail>(
				`/api/admin/libraries/builds/${buildId}`,
				token,
				projectId,
				{ refresh: true },
			);
		} catch {
			// 로드 실패 시 이전 값 유지
		} finally {
			loading = false;
		}
	}

	async function cancelBuild() {
		if (!buildId || cancelling) return;
		cancelling = true;
		cancelError = '';
		try {
			await api.post(
				`/api/admin/libraries/builds/${buildId}/cancel`,
				{},
				token,
				projectId,
			);
			onCancelled?.();
			await loadDetail();
		} catch (e) {
			cancelError = e instanceof ApiError ? e.message : '취소 실패';
		} finally {
			cancelling = false;
		}
	}

	// buildId 변경 시 상세 로드
	$effect(() => {
		if (open && buildId) {
			loadDetail();
		} else {
			detail = null;
		}
	});

	// 진행 중 빌드 폴링 (10초)
	$effect(() => {
		if (!open || !buildId) return;
		const interval = setInterval(() => {
			if (isActive) loadDetail();
		}, 10_000);
		return () => clearInterval(interval);
	});

	function fmtDate(iso: string | null | undefined): string {
		if (!iso) return '—';
		return new Date(iso).toLocaleString('ko-KR');
	}

	function elapsed(started: string | null | undefined): string {
		if (!started) return '—';
		const ms = Date.now() - new Date(started).getTime();
		const s = Math.floor(ms / 1000);
		if (s < 60) return `${s}초`;
		const m = Math.floor(s / 60);
		if (m < 60) return `${m}분 ${s % 60}초`;
		return `${Math.floor(m / 60)}시간 ${m % 60}분`;
	}
</script>

<Modal bind:open>
	{#if detail || loading}
		<div class="bg-gray-900 rounded-xl border border-gray-700 w-full max-w-2xl mx-auto p-6 space-y-5">
			<!-- 헤더 -->
			<div class="flex items-start justify-between gap-3">
				<div>
					<p class="text-xs text-gray-500 mb-1">라이브러리 빌드 상세</p>
					<h2 class="text-base font-semibold text-white">{detail?.library_id ?? '—'}</h2>
				</div>
				<div class="flex items-center gap-2 shrink-0">
					{#if detail?.status}
						<StatusChip status={detail.status} />
					{/if}
					{#if detail?.cloud_init_status}
						<StatusChip status={detail.cloud_init_status} />
					{/if}
					<button
						onclick={() => (open = false)}
						class="text-gray-500 hover:text-white transition-colors ml-2"
						aria-label="닫기"
					>
						<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
						</svg>
					</button>
				</div>
			</div>

			{#if loading && !detail}
				<div class="space-y-2">
					{#each [1, 2, 3] as _}
						<div class="h-8 bg-gray-800 rounded animate-pulse"></div>
					{/each}
				</div>
			{:else if detail}
				<!-- 진행률 바 -->
				<div>
					<div class="flex justify-between text-xs text-gray-400 mb-1">
						<span>{detail.progress_step || '대기 중'}</span>
						<span>{detail.progress_pct}%</span>
					</div>
					<div class="h-1.5 bg-gray-700 rounded-full overflow-hidden">
						<div
							class="h-full rounded-full transition-all duration-500 {detail.status === 'complete' ? 'bg-green-500' : detail.status === 'error' || detail.status === 'cancelled' ? 'bg-red-500' : 'bg-blue-500'}"
							style="width: {detail.progress_pct}%"
						></div>
					</div>
				</div>

				<!-- VM·빌드 정보 그리드 -->
				<div class="grid grid-cols-2 gap-3 text-xs">
					<div class="bg-gray-800/60 rounded-lg px-3 py-2.5">
						<p class="text-gray-500 mb-0.5">VM 인스턴스</p>
						<p class="text-white font-mono truncate">{detail.server_id ? detail.server_id.slice(0, 18) + '…' : '—'}</p>
					</div>
					<div class="bg-gray-800/60 rounded-lg px-3 py-2.5">
						<p class="text-gray-500 mb-0.5">VM 상태</p>
						{#if detail.vm_status}
							<StatusChip status={detail.vm_status.toLowerCase()} />
						{:else}
							<p class="text-gray-400">—</p>
						{/if}
					</div>
					<div class="bg-gray-800/60 rounded-lg px-3 py-2.5">
						<p class="text-gray-500 mb-0.5">VM IP</p>
						<p class="text-white font-mono">{detail.vm_ip ?? '—'}</p>
					</div>
					<div class="bg-gray-800/60 rounded-lg px-3 py-2.5">
						<p class="text-gray-500 mb-0.5">경과 시간</p>
						<p class="text-white">{elapsed(detail.started_at)}</p>
					</div>
					<div class="bg-gray-800/60 rounded-lg px-3 py-2.5">
						<p class="text-gray-500 mb-0.5">시작 시각</p>
						<p class="text-white">{fmtDate(detail.started_at)}</p>
					</div>
					<div class="bg-gray-800/60 rounded-lg px-3 py-2.5">
						<p class="text-gray-500 mb-0.5">완료 시각</p>
						<p class="text-white">{fmtDate(detail.completed_at)}</p>
					</div>
					{#if detail.file_storage_id}
						<div class="col-span-2 bg-gray-800/60 rounded-lg px-3 py-2.5">
							<p class="text-gray-500 mb-0.5">Manila Share ID</p>
							<p class="text-white font-mono text-[11px] truncate">{detail.file_storage_id}</p>
						</div>
					{/if}
				</div>

				<!-- 에러 메시지 -->
				{#if detail.error_message}
					<div class="bg-red-900/30 border border-red-700/50 rounded-lg px-3 py-2.5">
						<p class="text-xs text-red-400 font-medium mb-1">오류</p>
						<p class="text-xs text-red-300 font-mono whitespace-pre-wrap break-all">{detail.error_message}</p>
					</div>
				{/if}

				<!-- 콘솔 로그 -->
				<div>
					<div class="flex items-center justify-between mb-1.5">
						<p class="text-xs text-gray-500">
							{#if detail.live_console}
								콘솔 로그 {isActive ? '(10초마다 자동 갱신)' : ''}
							{:else if detail.console_log_excerpt}
								마지막 저장 로그
							{:else}
								콘솔 로그
							{/if}
						</p>
						{#if isActive}
							<button
								onclick={loadDetail}
								class="text-[11px] text-blue-400 hover:text-blue-300 transition-colors"
							>새로고침</button>
						{/if}
					</div>
					{#if detail.live_console || detail.console_log_excerpt}
						<pre class="bg-gray-950 text-[11px] text-gray-300 font-mono whitespace-pre-wrap break-all overflow-auto max-h-56 rounded-lg p-3 border border-gray-800">{detail.live_console || detail.console_log_excerpt}</pre>
					{:else}
						<div class="bg-gray-950 rounded-lg p-3 border border-gray-800 text-[11px] text-gray-500 font-mono">
							{detail.console_note || '로그 없음'}
						</div>
					{/if}
				</div>

				<!-- 하단 액션 -->
				<div class="flex items-center justify-between pt-1 border-t border-gray-800">
					{#if cancelError}
						<p class="text-xs text-red-400">{cancelError}</p>
					{:else}
						<div></div>
					{/if}
					<div class="flex gap-2">
						{#if isActive}
							<button
								onclick={cancelBuild}
								disabled={cancelling}
								class="px-3 py-1.5 text-xs text-red-400 border border-red-700/50 hover:bg-red-900/30 disabled:opacity-50 rounded-lg transition-colors"
							>
								{cancelling ? '취소 중...' : '빌드 취소'}
							</button>
						{/if}
						<button
							onclick={() => (open = false)}
							class="px-3 py-1.5 text-xs text-gray-400 border border-gray-700 hover:bg-gray-800 rounded-lg transition-colors"
						>닫기</button>
					</div>
				</div>
			{/if}
		</div>
	{/if}
</Modal>
