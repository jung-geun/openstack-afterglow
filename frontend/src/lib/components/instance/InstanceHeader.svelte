<script lang="ts">
	import DetailHeader from '$lib/components/ui/DetailHeader.svelte';
	import { useInstanceDetailController } from '$lib/stores/instanceDetailController.svelte';

	interface Props {
		adminProjectId: string | null;
		onOpenMigrateModal: (type: 'live' | 'cold') => void;
		onOpenPasswordModal: () => void;
		onOpenResizeModal: () => void;
	}

	let { adminProjectId, onOpenMigrateModal, onOpenPasswordModal, onOpenResizeModal }: Props = $props();

	const s = useInstanceDetailController();
</script>

<DetailHeader title={s.instance!.name} status={s.instance!.status} size="lg">
	{#snippet meta()}
		{#if s.instance!.status === 'ERROR' && s.instance!.fault?.message && adminProjectId}
			<div class="p-3 rounded-lg bg-red-900/30 border border-red-800/40 text-red-300 text-sm max-w-xl">
				<div class="font-medium mb-1 text-xs text-red-400">오류 상세 (관리자)</div>
				<div class="text-xs opacity-90 break-words">{s.instance!.fault!.message}</div>
			</div>
		{/if}
	{/snippet}
	{#snippet actions()}
		{#if s.instance!.status === 'SHUTOFF'}
			<button
				onclick={() => s.performAction('start')}
				disabled={!!s.actioning}
				class="text-green-400 hover:text-green-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-green-900 hover:border-green-700 disabled:border-gray-700 transition-colors"
			>
				{s.actioning === 'start' ? '시작 중...' : '시작'}
			</button>
		{/if}
		{#if s.instance!.status === 'SHELVED_OFFLOADED' || s.instance!.status === 'SHELVED'}
			<button
				onclick={() => s.performAction('unshelve')}
				disabled={!!s.actioning}
				class="text-green-400 hover:text-green-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-green-900 hover:border-green-700 disabled:border-gray-700 transition-colors"
			>
				{s.actioning === 'unshelve' ? '보관 해제 중...' : '보관 해제'}
			</button>
		{/if}
		{#if s.instance!.status === 'ACTIVE'}
			<button
				onclick={s.openConsole}
				class="text-gray-300 hover:text-white text-sm px-3 py-1.5 rounded border border-gray-700 hover:border-gray-500 transition-colors"
			>
				콘솔 열기
			</button>
			<button
				onclick={() => s.performAction('stop')}
				disabled={!!s.actioning}
				class="text-yellow-400 hover:text-yellow-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-yellow-900 hover:border-yellow-700 disabled:border-gray-700 transition-colors"
			>
				{s.actioning === 'stop' ? '정지 중...' : '정지'}
			</button>
			<button
				onclick={() => s.performAction('reboot')}
				disabled={!!s.actioning}
				class="text-blue-400 hover:text-blue-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-blue-900 hover:border-blue-700 disabled:border-gray-700 transition-colors"
			>
				{s.actioning === 'reboot' ? '재부팅 중...' : '재부팅'}
			</button>
		{/if}
		{#if s.instance!.status === 'ACTIVE' || s.instance!.status === 'SHUTOFF'}
			<button
				onclick={() => s.performAction('shelve')}
				disabled={!!s.actioning}
				class="text-purple-400 hover:text-purple-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-purple-900 hover:border-purple-700 disabled:border-gray-700 transition-colors"
			>
				{s.actioning === 'shelve' ? '보관 중...' : '보관'}
			</button>
		{/if}
		{#if adminProjectId}
			{#if s.instance!.status === 'ACTIVE'}
				<button
					onclick={() => onOpenMigrateModal('live')}
					disabled={!!s.actioning}
					class="text-cyan-400 hover:text-cyan-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-cyan-900 hover:border-cyan-700 disabled:border-gray-700 transition-colors"
				>
					라이브 마이그레이션
				</button>
			{/if}
			{#if s.instance!.status === 'ACTIVE' || s.instance!.status === 'SHUTOFF'}
				<button
					onclick={() => onOpenMigrateModal('cold')}
					disabled={!!s.actioning}
					class="text-teal-400 hover:text-teal-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-teal-900 hover:border-teal-700 disabled:border-gray-700 transition-colors"
				>
					콜드 마이그레이션
				</button>
				<button
					onclick={onOpenResizeModal}
					disabled={!!s.actioning}
					class="text-violet-400 hover:text-violet-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-violet-900 hover:border-violet-700 disabled:border-gray-700 transition-colors"
				>
					리사이즈
				</button>
			{/if}
			{#if s.instance!.status === 'VERIFY_RESIZE'}
				<button
					onclick={s.confirmResize}
					disabled={!!s.actioning}
					class="text-orange-400 hover:text-orange-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-orange-900 hover:border-orange-700 disabled:border-gray-700 transition-colors"
				>
					{s.actioning === 'confirm-resize' ? '확인 중...' : '리사이즈 확인'}
				</button>
				<button
					onclick={s.revertResize}
					disabled={!!s.actioning}
					class="text-yellow-400 hover:text-yellow-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-yellow-900 hover:border-yellow-700 disabled:border-gray-700 transition-colors"
				>
					{s.actioning === 'revert-resize' ? '취소 중...' : '되돌리기'}
				</button>
			{/if}
			<button
				onclick={onOpenPasswordModal}
				disabled={s.passwordPrecheckLoading || !s.passwordPrecheck?.supported}
				title={s.passwordPrecheck?.reason ?? (s.passwordPrecheckLoading ? '점검 중...' : '')}
				class="text-amber-400 hover:text-amber-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-amber-900 hover:border-amber-700 disabled:border-gray-700 transition-colors"
			>
				{s.passwordPrecheckLoading ? '점검 중...' : '비밀번호 재설정'}
			</button>
		{/if}
		<button
			onclick={s.deleteInstance}
			disabled={s.deleting}
			class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors"
		>
			{s.deleting ? '삭제 중...' : '삭제'}
		</button>
	{/snippet}
</DetailHeader>
