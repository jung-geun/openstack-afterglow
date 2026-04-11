<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';

	interface Profile {
		id: string;
		name: string;
		email: string;
		description: string;
		default_project_id: string;
	}

	interface Project {
		id: string;
		name: string;
		description?: string;
	}

	let { open = false, onclose }: { open?: boolean; onclose?: () => void } = $props();

	let profile = $state<Profile>({ id: '', name: '', email: '', description: '', default_project_id: '' });
	let loading = $state(false);
	let profileError = $state('');
	let profileSuccess = $state('');
	let profileSaving = $state(false);

	let editName = $state('');
	let editEmail = $state('');
	let editDescription = $state('');
	let editDefaultProjectId = $state('');

	let currentPassword = $state('');
	let newPassword = $state('');
	let confirmPassword = $state('');
	let pwError = $state('');
	let pwSuccess = $state('');
	let pwSaving = $state(false);

	let projects = $state<Project[]>([]);

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
			editDefaultProjectId = res.default_project_id || '';
		} catch (e) {
			profileError = e instanceof ApiError ? e.message : '프로필을 불러올 수 없습니다';
		} finally {
			loading = false;
		}
	}

	async function loadProjects() {
		if (!token) return;
		try {
			projects = await api.get<Project[]>('/api/auth/projects', token);
		} catch { /* ignore */ }
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
			if (editDefaultProjectId !== profile.default_project_id) body.default_project_id = editDefaultProjectId;
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

	function close() {
		onclose?.();
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') close();
	}

	$effect(() => {
		if (open) {
			loadProfile();
			loadProjects();
		} else {
			// 닫힐 때 메시지 초기화
			profileError = '';
			profileSuccess = '';
			pwError = '';
			pwSuccess = '';
		}
	});
</script>

<svelte:window onkeydown={handleKeydown} />

{#if open}
<div class="fixed inset-0 z-50 flex items-start justify-center pt-16 sm:items-center sm:pt-0">
	<!-- backdrop -->
	<button
		class="absolute inset-0 bg-black/60"
		onclick={close}
		aria-label="닫기"
		tabindex="-1"
	></button>

	<!-- panel -->
	<div class="relative bg-gray-950 border border-gray-800 rounded-2xl w-full max-w-lg mx-4 max-h-[85vh] overflow-y-auto shadow-2xl">
		<!-- 헤더 -->
		<div class="flex items-center justify-between px-6 py-4 border-b border-gray-800 sticky top-0 bg-gray-950 z-10">
			<h2 class="text-lg font-bold text-white">계정 설정</h2>
			<button onclick={close} class="text-gray-400 hover:text-white transition-colors p-1 rounded-lg hover:bg-gray-800">
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
				</svg>
			</button>
		</div>

		<div class="p-6 space-y-6">
			{#if loading}
				<div class="space-y-3">
					{#each [1,2,3] as _}
						<div class="h-10 bg-gray-800 rounded animate-pulse"></div>
					{/each}
				</div>
			{:else}
				<!-- 프로필 섹션 -->
				<div class="bg-gray-900 border border-gray-800 rounded-xl p-5">
					<h3 class="text-sm font-semibold text-white mb-4">프로필 정보</h3>

					{#if profileError}
						<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-3 py-2 text-xs mb-3">{profileError}</div>
					{/if}
					{#if profileSuccess}
						<div class="bg-green-900/40 border border-green-700 text-green-300 rounded-lg px-3 py-2 text-xs mb-3">{profileSuccess}</div>
					{/if}

					<div class="space-y-3">
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
						{#if projects.length > 0}
						<div>
							<label class="block text-xs text-gray-400 mb-1">기본 프로젝트</label>
							<select
								bind:value={editDefaultProjectId}
								class="w-full bg-gray-800 border border-gray-700 focus:border-blue-500 text-white text-sm rounded-lg px-3 py-2 outline-none transition-colors"
							>
								<option value="">선택 안 함</option>
								{#each projects as p}
									<option value={p.id}>{p.name}</option>
								{/each}
							</select>
						</div>
						{/if}
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
				<div class="bg-gray-900 border border-gray-800 rounded-xl p-5">
					<h3 class="text-sm font-semibold text-white mb-4">패스워드 변경</h3>

					{#if pwError}
						<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-3 py-2 text-xs mb-3">{pwError}</div>
					{/if}
					{#if pwSuccess}
						<div class="bg-green-900/40 border border-green-700 text-green-300 rounded-lg px-3 py-2 text-xs mb-3">{pwSuccess}</div>
					{/if}

					<div class="space-y-3">
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
	</div>
</div>
{/if}
