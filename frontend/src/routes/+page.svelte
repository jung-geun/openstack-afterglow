<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { auth, setAuth, isLoggedIn } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoginBrandHeader from '$lib/components/auth/LoginBrandHeader.svelte';
	import LoginForm from '$lib/components/auth/LoginForm.svelte';
	import type { LoginResponse } from '$lib/types/auth';

	onMount(async () => {
		try {
			const res = await api.get<{ enabled: boolean }>('/auth/gitlab/enabled');
			gitlabEnabled = res.enabled;
		} catch {
			gitlabEnabled = false;
		}
	});

	let domainName = $state('Default');
	let username = $state('');
	let password = $state('');
	let error = $state('');
	let loading = $state(false);
	let gitlabEnabled = $state(false);
	let gitlabLoading = $state(false);

	$effect(() => {
		if ($isLoggedIn) goto($auth.projectId ? '/dashboard' : '/select-project');
	});

	async function loginWithGitlab() {
		gitlabLoading = true;
		error = '';
		try {
			const res = await api.get<{ authorize_url: string }>('/auth/gitlab/authorize');
			// 안전한 프로토콜인지 확인 (오픈 리다이렉트 방지)
			const redirectUrl = new URL(res.authorize_url);
			if (!['https:', 'http:'].includes(redirectUrl.protocol)) {
				error = 'GitLab 인증 URL이 유효하지 않습니다';
				gitlabLoading = false;
				return;
			}
			window.location.href = res.authorize_url;
		} catch (e) {
			error = e instanceof ApiError ? `GitLab 인증 오류 (${e.status})` : 'GitLab 인증 URL 조회 실패';
			gitlabLoading = false;
		}
	}

	async function login() {
		error = '';
		loading = true;
		try {
			const data = await api.post<LoginResponse>('/api/v1/auth/login', {
				username, password, domain_name: domainName,
			});

			// 백엔드가 이미 기본 프로젝트(없으면 첫 번째 활성 프로젝트)로 scope된 토큰을 반환한다.
			// project_id 가 있으면 바로 대시보드로, 없으면 선택 화면으로 이동한다.
			setAuth({
				token: data.token,
				refreshToken: data.refresh_token ?? null,
				accessExpiresAt: data.expires_at
					? Math.floor(new Date(data.expires_at).getTime() / 1000)
					: null,
				userId: data.user_id,
				username: data.username,
				projectId: data.project_id || null,
				projectName: data.project_name || null,
				roles: data.roles ?? [],
				isSystemAdmin: data.is_system_admin ?? false,
			});
			// 라우팅은 $effect (isLoggedIn + auth.projectId 기반) 가 처리한다.
		} catch (e) {
			error = e instanceof ApiError ? `인증 실패 (${e.status})` : '서버 오류가 발생했습니다';
		} finally {
			loading = false;
		}
	}
</script>

<div class="min-h-screen bg-gray-900 flex items-center justify-center">
	<div class="w-full max-w-md px-4">
		<LoginBrandHeader />
		<LoginForm
			bind:domainName
			bind:username
			bind:password
			{error}
			{loading}
			gitlabEnabled={gitlabEnabled}
			gitlabLoading={gitlabLoading}
			onSubmit={login}
			onGitlab={loginWithGitlab}
		/>
	</div>
</div>
