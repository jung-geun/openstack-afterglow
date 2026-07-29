<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { auth, setAuth, isLoggedIn } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoginBrandHeader from '$lib/components/auth/LoginBrandHeader.svelte';
	import LoginForm from '$lib/components/auth/LoginForm.svelte';
	import type { LoginResponse } from '$lib/types/auth';
	import { resolvePostLoginProject } from '$lib/utils/authFlow';
	import { postAuthDestination } from '$lib/utils/mcpConsent';

	onMount(async () => {
		try {
			const res = await api.get<{ enabled: boolean }>('/api/v1/auth/gitlab/enabled');
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
		if ($isLoggedIn) {
			const fallback = $page.data.mockup?.active ? $page.data.mockup.homePath : ($auth.projectId ? '/dashboard' : '/select-project');
			goto(postAuthDestination(fallback));
		}
	});

	async function loginWithGitlab() {
		gitlabLoading = true;
		error = '';
		try {
			const res = await api.get<{ authorize_url: string }>('/api/v1/auth/gitlab/authorize');
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
			const resolution = resolvePostLoginProject(data);
			const scopedProjectId = data.project_id?.trim() || null;

			setAuth({
				token: data.token,
				refreshToken: data.refresh_token ?? null,
				accessExpiresAt: data.expires_at
					? Math.floor(new Date(data.expires_at).getTime() / 1000)
					: null,
				userId: data.user_id,
				username: data.username,
				projectId: resolution.projectId,
				projectName: resolution.projectId === scopedProjectId ? (data.project_name || null) : null,
				roles: data.roles ?? [],
				isSystemAdmin: data.is_system_admin ?? false,
			});
			await goto(postAuthDestination(resolution.target));
		} catch (e) {
			error = e instanceof ApiError ? `인증 실패 (${e.status})` : '서버 오류가 발생했습니다';
		} finally {
			loading = false;
		}
	}
</script>

<div class="login-page">
	<div class="login-shell">
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

<style>
	.login-page {
		min-height: 100vh;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 1rem;
		background: var(--color-surface-canvas);
		color: var(--color-ink-0);
	}

	.login-shell {
		width: 100%;
		max-width: 28rem;
	}
</style>
