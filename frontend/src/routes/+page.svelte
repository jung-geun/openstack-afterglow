<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { setAuth, setAvailableProjects, isLoggedIn } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import { loadSiteConfig } from '$lib/config/site';
	import LoginBrandHeader from '$lib/components/auth/LoginBrandHeader.svelte';
	import LoginForm from '$lib/components/auth/LoginForm.svelte';
	import type { Project, LoginResponse } from '$lib/types/auth';

	onMount(async () => {
		loadSiteConfig();
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
		if ($isLoggedIn) goto('/dashboard');
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

			let projects: Project[] = [];
			try {
				projects = await api.get<Project[]>('/api/v1/auth/projects', data.token);
			} catch { /* 프로젝트 목록 조회 실패 시 무시 */ }

			let selectedProjectId: string | null = null;
			let selectedProjectName: string | null = null;

			if (data.default_project_id && projects.length > 0) {
				const defaultProject = projects.find(p => p.id === data.default_project_id);
				if (defaultProject) {
					selectedProjectId = defaultProject.id;
					selectedProjectName = defaultProject.name;
				}
			}
			if (!selectedProjectId && projects.length === 1) {
				selectedProjectId = projects[0].id;
				selectedProjectName = projects[0].name;
			}

			setAuth({
				token: data.token,
				refreshToken: data.refresh_token ?? null,
				accessExpiresAt: data.expires_at
					? Math.floor(new Date(data.expires_at).getTime() / 1000)
					: null,
				userId: data.user_id,
				username: data.username,
				projectId: selectedProjectId,
				projectName: selectedProjectName,
				roles: data.roles ?? [],
				isSystemAdmin: data.is_system_admin ?? false,
			});
			setAvailableProjects(projects);
			goto(selectedProjectId ? '/dashboard' : '/select-project');
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
