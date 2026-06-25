<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { api } from '$lib/api/client';

	interface Props {
		serverId: string;
		serverName: string;
		currentHost?: string | null;
		onClose: () => void;
		onEvacuated?: () => void;
	}

	let { serverId, serverName, currentHost, onClose, onEvacuated }: Props = $props();

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	type Phase = 'idle' | 'executing' | 'done' | 'error';
	let phase = $state<Phase>('idle');
	let host = $state('');
	let onSharedStorage = $state(false);
	let errorMsg = $state('');
	let confirmed = $state(false);

	async function execute() {
		if (!confirmed) return;
		phase = 'executing';
		try {
			await api.post(
				`/api/v1/admin/instances/${serverId}/evacuate`,
				{ host: host.trim() || null, on_shared_storage: onSharedStorage },
				token,
				projectId,
			);
			phase = 'done';
			onEvacuated?.();
		} catch (e: unknown) {
			errorMsg = e instanceof Error ? e.message : '강제 이주 중 오류가 발생했습니다';
			phase = 'error';
		}
	}
</script>

<div
	class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
	role="dialog"
	aria-modal="true"
	aria-label="인스턴스 강제 이주"
>
	<div class="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-lg shadow-2xl">
		<!-- 헤더 -->
		<div class="flex items-center justify-between px-6 py-4 border-b border-gray-800">
			<div>
				<h2 class="text-white font-semibold text-base">인스턴스 강제 이주 (Evacuate)</h2>
				<p class="text-gray-400 text-xs mt-0.5 font-mono">{serverName} · {serverId.slice(0, 8)}</p>
			</div>
			<button onclick={onClose} class="text-gray-500 hover:text-gray-300 transition-colors text-lg leading-none">✕</button>
		</div>

		<div class="px-6 py-5 space-y-4">

			<!-- 설명 -->
			<div class="bg-amber-900/20 border border-amber-700/40 text-amber-300 rounded-lg px-4 py-3 text-xs leading-relaxed">
				<span class="font-medium">주의:</span> Evacuate는 호스트 장애 시 인스턴스를 다른 호스트로 강제 이주합니다.
				인스턴스가 정상 호스트에 있으면 데이터 불일치가 발생할 수 있습니다.
			</div>

			{#if currentHost}
				<div class="text-xs text-gray-400">
					현재 호스트: <span class="text-gray-200 font-mono">{currentHost}</span>
				</div>
			{/if}

			<!-- 에러 -->
			{#if phase === 'error'}
				<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">
					{errorMsg}
				</div>
			{/if}

			<!-- 완료 -->
			{#if phase === 'done'}
				<div class="bg-green-900/30 border border-green-700/50 text-green-300 rounded-lg px-4 py-3 text-sm">
					강제 이주 요청이 전송되었습니다. 인스턴스 상태가 REBUILD로 전이됩니다.
				</div>
			{:else if phase !== 'executing'}
				<!-- 폼 -->
				<div class="space-y-3">
					<div>
						<label for="evacuate-host" class="block text-xs text-gray-400 mb-1 font-medium">
							대상 호스트 <span class="text-gray-600">(비워두면 스케줄러 자동 선택)</span>
						</label>
						<input
							id="evacuate-host"
							type="text"
							bind:value={host}
							placeholder="예: compute01.example.com"
							class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-blue-500"
						/>
					</div>

					<label class="flex items-start gap-3 cursor-pointer select-none">
						<input
							type="checkbox"
							bind:checked={onSharedStorage}
							class="mt-0.5 rounded border-gray-600 bg-gray-800 text-blue-500 focus:ring-blue-500 focus:ring-1"
						/>
						<div>
							<div class="text-sm text-gray-300">공유 스토리지 사용 (onSharedStorage)</div>
							<div class="text-xs text-gray-500 mt-0.5">
								인스턴스 디스크가 공유 스토리지(Ceph RBD 등)에 있으면 활성화. 그 외에는 비활성.
							</div>
						</div>
					</label>
				</div>
			{/if}

			<!-- 실행 중 -->
			{#if phase === 'executing'}
				<div class="flex items-center gap-3 text-gray-400 text-sm py-4 justify-center">
					<svg class="animate-spin w-5 h-5 text-amber-400" fill="none" viewBox="0 0 24 24">
						<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
						<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
					</svg>
					강제 이주 요청 중…
				</div>
			{/if}
		</div>

		<!-- 푸터 -->
		<div class="flex items-center justify-between px-6 py-4 border-t border-gray-800 gap-4">
			{#if phase === 'idle' || phase === 'error'}
				<label class="flex items-center gap-2 text-sm text-gray-300 cursor-pointer select-none">
					<input
						type="checkbox"
						bind:checked={confirmed}
						class="rounded border-gray-600 bg-gray-800 text-amber-500 focus:ring-amber-500 focus:ring-1"
					/>
					<span>호스트 장애 상황임을 확인했습니다.</span>
				</label>
				<button
					onclick={execute}
					disabled={!confirmed}
					class="shrink-0 px-4 py-2 bg-amber-700 hover:bg-amber-600 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors"
				>
					강제 이주 실행
				</button>
			{:else}
				<div></div>
				<button
					onclick={onClose}
					class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg transition-colors"
				>
					닫기
				</button>
			{/if}
		</div>
	</div>
</div>
