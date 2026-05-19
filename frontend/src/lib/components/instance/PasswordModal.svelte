<script lang="ts">
	import { useInstanceDetailController } from '$lib/stores/instanceDetailController.svelte';

	interface Props {
		onClose: () => void;
	}

	let { onClose }: Props = $props();

	const s = useInstanceDetailController();

	let newPassword = $state('');
	let confirmPassword = $state('');
	let passwordError = $state('');

	async function handleSetPassword() {
		if (newPassword !== confirmPassword) {
			passwordError = '패스워드가 일치하지 않습니다';
			return;
		}
		if (newPassword.length < 8) {
			passwordError = '패스워드는 8자 이상이어야 합니다';
			return;
		}
		passwordError = '';
		const err = await s.doSetPassword(newPassword);
		if (err) {
			passwordError = err;
		} else {
			onClose();
		}
	}
</script>

<div
	class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
	role="dialog"
	onclick={onClose}
	onkeydown={(e) => e.key === 'Escape' && onClose()}
	tabindex="-1"
>
	<div
		class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl"
		onclick={(e) => e.stopPropagation()}
		role="document"
	>
		<h3 class="text-white font-semibold text-lg mb-1">관리자 비밀번호 재설정</h3>
		<p class="text-gray-400 text-sm mb-4">인스턴스: <span class="text-white">{s.instance?.name}</span></p>
		{#if s.passwordPrecheck?.os_admin_user}
			<p class="text-xs text-gray-500 mb-4">대상 계정: <span class="text-amber-400">{s.passwordPrecheck.os_admin_user}</span> (이미지 메타 기준)</p>
		{:else}
			<p class="text-xs text-gray-500 mb-4">대상 계정: 이미지 메타데이터의 <code class="text-amber-400">os_admin_user</code>로 자동 결정</p>
		{/if}
		<div class="bg-yellow-900/20 border border-yellow-800/40 rounded-lg p-3 mb-4 text-xs text-yellow-300">
			QGA가 게스트에 실제로 동작 중이어야 변경이 적용됩니다. 변경 직후 콘솔/SSH로 동작을 확인하세요.
		</div>
		<div class="space-y-3 mb-4">
			<div>
				<label class="block text-sm text-gray-400 mb-1" for="new-password">새 비밀번호</label>
				<input
					id="new-password"
					type="password"
					bind:value={newPassword}
					placeholder="8자 이상"
					class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-amber-500"
				/>
			</div>
			<div>
				<label class="block text-sm text-gray-400 mb-1" for="confirm-password">비밀번호 확인</label>
				<input
					id="confirm-password"
					type="password"
					bind:value={confirmPassword}
					placeholder="동일한 비밀번호 재입력"
					class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-amber-500"
				/>
			</div>
		</div>
		{#if passwordError}
			<p class="text-red-400 text-sm mb-3">{passwordError}</p>
		{/if}
		<div class="bg-gray-800/60 border border-gray-700/40 rounded-lg p-3 mb-4 text-xs text-gray-400">
			<span class="text-gray-300 font-medium">SSH 키 런타임 주입 안내:</span>
			표준 OpenStack은 실행 중 SSH 키 주입을 지원하지 않습니다.
			키페어 사전 등록은 <a href="/dashboard/compute/keypairs" class="text-cyan-400 hover:underline">키페어 관리</a>에서, 비상 복구는 rebuild를 사용하세요.
		</div>
		<div class="flex justify-end gap-3">
			<button onclick={onClose} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">취소</button>
			<button
				onclick={handleSetPassword}
				disabled={s.passwordPrecheckLoading || !newPassword || !confirmPassword}
				class="px-4 py-2 bg-amber-700 hover:bg-amber-600 text-white text-sm font-medium rounded-lg disabled:opacity-30"
			>
				{s.passwordPrecheckLoading ? '변경 중...' : '변경'}
			</button>
		</div>
	</div>
</div>
