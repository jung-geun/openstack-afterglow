<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';

	interface Profile {
		id: string;
		name: string;
		email: string;
		description: string;
	}

	let profile = $state<Profile>({ id: '', name: '', email: '', description: '' });
	let loading = $state(true);
	let profileError = $state('');
	let profileSuccess = $state('');
	let profileSaving = $state(false);

	// 편집용 필드
	let editName = $state('');
	let editEmail = $state('');
	let editDescription = $state('');

	// 패스워드 변경
	let currentPassword = $state('');
	let newPassword = $state('');
	let confirmPassword = $state('');
	let pwError = $state('');
	let pwSuccess = $state('');
	let pwSaving = $state(false);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function loadProfile() {
		loading = true;
		profileError = '';
		try {
			const res = await api.get<Profile>('/api/profile', token, projectId);
			profile = res;
			editName = res.name;
			editEmail = res.email;
			editDescription = res.description;
		} catch (e) {
			profileError = e instanceof ApiError ? e.message : '프로필을 불러올 수 없습니다';
		} finally {
			loading = false;
		}
	}

	async function saveProfile() {
		profileError = '';
		profileSuccess = '';
		profileSaving = true;
		try {
			const body: Record<string, string> = {};
			if (editName !== profile.name) body.name = editName;
			if (editEmail !== profile.email) body.email = editEmail;
			if (editDescription !== profile.description) body.description = editDescription;
			if (Object.keys(body).length === 0) {
				profileError = '변경된 내용이 없습니다';
				return;
			}
			const res = await api.patch<Profile>('/api/profile', body, token, projectId);
			profile = res;
			profileSuccess = '프로필이 저장되었습니다';
		} catch (e) {
			profileError = e instanceof ApiError ? e.message : '저장 실패';
		} finally {
			profileSaving = false;
		}
	}

	async function changePassword() {
		pwError = '';
		pwSuccess = '';
		if (!currentPassword || !newPassword || !confirmPassword) {
			pwError = '모든 항목을 입력해 주세요';
			return;
		}
		if (newPassword !== confirmPassword) {
			pwError = '새 패스워드가 일치하지 않습니다';
			return;
		}
		if (newPassword.length < 8) {
			pwError = '새 패스워드는 8자 이상이어야 합니다';
			return;
		}
		pwSaving = true;
		try {
			await api.post('/api/profile/password', {
				current_password: currentPassword,
				new_password: newPassword,
			}, token, projectId);
			pwSuccess = '패스워드가 변경되었습니다';
			currentPassword = '';
			newPassword = '';
			confirmPassword = '';
		} catch (e) {
			pwError = e instanceof ApiError ? e.message : '패스워드 변경 실패';
		} finally {
			pwSaving = false;
		}
	}

	onMount(loadProfile);
</script>

<div class="p-4 md:p-8 max-w-2xl">
	<h1 class="text-2xl font-bold text-white mb-6">계정 설정</h1>

	{#if loading}
		<div class="space-y-4">
			{#each [1,2,3] as _}
				<div class="h-10 bg-gray-800 rounded animate-pulse"></div>
			{/each}
		</div>
	{:else}
		<!-- 프로필 섹션 -->
		<div class="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-6">
			<h2 class="text-base font-semibold text-white mb-4">프로필 정보</h2>

			{#if profileError}
				<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{profileError}</div>
			{/if}
			{#if profileSuccess}
				<div class="bg-green-900/40 border border-green-700 text-green-300 rounded-lg px-4 py-3 text-sm mb-4">{profileSuccess}</div>
			{/if}

			<div class="space-y-4">
				<div>
					<label class="block text-xs text-gray-400 mb-1">사용자 ID</label>
					<div class="text-sm text-gray-500 font-mono bg-gray-800/50 rounded px-3 py-2">{profile.id}</div>
				</div>
				<div>
					<label class="block text-xs text-gray-400 mb-1">이름 (닉네임)</label>
					<input
						type="text"
						bind:value={editName}
						class="w-full bg-gray-800 border border-gray-700 focus:border-blue-500 text-white text-sm rounded-lg px-3 py-2 outline-none transition-colors"
						placeholder="이름 입력"
					/>
				</div>
				<div>
					<label class="block text-xs text-gray-400 mb-1">이메일</label>
					<input
						type="email"
						bind:value={editEmail}
						class="w-full bg-gray-800 border border-gray-700 focus:border-blue-500 text-white text-sm rounded-lg px-3 py-2 outline-none transition-colors"
						placeholder="이메일 입력"
					/>
				</div>
				<div>
					<label class="block text-xs text-gray-400 mb-1">설명</label>
					<textarea
						bind:value={editDescription}
						rows="2"
						class="w-full bg-gray-800 border border-gray-700 focus:border-blue-500 text-white text-sm rounded-lg px-3 py-2 outline-none transition-colors resize-none"
						placeholder="설명 입력 (선택)"
					></textarea>
				</div>
			</div>

			<div class="mt-4 flex justify-end">
				<button
					onclick={saveProfile}
					disabled={profileSaving}
					class="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm rounded-lg transition-colors"
				>
					{profileSaving ? '저장 중...' : '저장'}
				</button>
			</div>
		</div>

		<!-- 패스워드 변경 섹션 -->
		<div class="bg-gray-900 border border-gray-800 rounded-xl p-6">
			<h2 class="text-base font-semibold text-white mb-4">패스워드 변경</h2>

			{#if pwError}
				<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{pwError}</div>
			{/if}
			{#if pwSuccess}
				<div class="bg-green-900/40 border border-green-700 text-green-300 rounded-lg px-4 py-3 text-sm mb-4">{pwSuccess}</div>
			{/if}

			<div class="space-y-4">
				<div>
					<label class="block text-xs text-gray-400 mb-1">현재 패스워드</label>
					<input
						type="password"
						bind:value={currentPassword}
						class="w-full bg-gray-800 border border-gray-700 focus:border-blue-500 text-white text-sm rounded-lg px-3 py-2 outline-none transition-colors"
						placeholder="현재 패스워드"
					/>
				</div>
				<div>
					<label class="block text-xs text-gray-400 mb-1">새 패스워드</label>
					<input
						type="password"
						bind:value={newPassword}
						class="w-full bg-gray-800 border border-gray-700 focus:border-blue-500 text-white text-sm rounded-lg px-3 py-2 outline-none transition-colors"
						placeholder="8자 이상"
					/>
				</div>
				<div>
					<label class="block text-xs text-gray-400 mb-1">새 패스워드 확인</label>
					<input
						type="password"
						bind:value={confirmPassword}
						class="w-full bg-gray-800 border border-gray-700 focus:border-blue-500 text-white text-sm rounded-lg px-3 py-2 outline-none transition-colors"
						placeholder="패스워드 재입력"
					/>
				</div>
			</div>

			<div class="mt-4 flex justify-end">
				<button
					onclick={changePassword}
					disabled={pwSaving}
					class="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm rounded-lg transition-colors"
				>
					{pwSaving ? '변경 중...' : '패스워드 변경'}
				</button>
			</div>
		</div>
	{/if}
</div>
