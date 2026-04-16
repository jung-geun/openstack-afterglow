<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { setAuth, setAvailableProjects, isLoggedIn } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import { siteConfig, loadSiteConfig } from '$lib/config/site';

	onMount(async () => {
		loadSiteConfig();
		try {
			const res = await api.get<{ enabled: boolean }>('/api/auth/gitlab/enabled');
			gitlabEnabled = res.enabled;
		} catch {
			gitlabEnabled = false;
		}
	});

	interface Project {
		id: string;
		name: string;
		description?: string;
	}

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
			const res = await api.get<{ authorize_url: string }>('/api/auth/gitlab/authorize');
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
			const data = await api.post<{
				token: string;
				user_id: string;
				username: string;
				project_id: string;
				project_name: string;
				expires_at: string | null;
				roles?: string[];
				default_project_id?: string;
			}>('/api/auth/login', { username, password, domain_name: domainName });

			// 프로젝트 목록 조회
			let projects: Project[] = [];
			try {
				projects = await api.get<Project[]>('/api/auth/projects', data.token);
			} catch {
				// 프로젝트 목록 조회 실패 시 무시
			}

			// 세션 설정 조회
			let sessionTimeoutSeconds = 3600;
			let sessionWarningBeforeSeconds = 300;
			try {
				const sessionInfo = await api.get<{ timeout_seconds: number; warning_before_seconds: number }>(
					'/api/auth/session-info', data.token, data.project_id
				);
				sessionTimeoutSeconds = sessionInfo.timeout_seconds;
				sessionWarningBeforeSeconds = sessionInfo.warning_before_seconds;
			} catch {
				// 기본값 유지
			}

			// 기본 프로젝트가 설정되어 있고, 프로젝트 목록에 존재하면 해당 프로젝트로 전환
			let selectedProjectId = data.project_id;
			let selectedProjectName = data.project_name;
			if (data.default_project_id && projects.length > 0) {
				const defaultProject = projects.find(p => p.id === data.default_project_id);
				if (defaultProject) {
					selectedProjectId = defaultProject.id;
					selectedProjectName = defaultProject.name;
				}
			}

			setAuth({
				token: data.token,
				userId: data.user_id,
				username: data.username,
				projectId: selectedProjectId,
				projectName: selectedProjectName,
				expiresAt: data.expires_at ?? null,
				sessionTimeoutSeconds,
				sessionWarningBeforeSeconds,
				roles: data.roles ?? [],
				isSystemAdmin: data.is_system_admin ?? false,
			});
			setAvailableProjects(projects);
			goto('/dashboard');
		} catch (e) {
			error = e instanceof ApiError ? `인증 실패 (${e.status})` : '서버 오류가 발생했습니다';
		} finally {
			loading = false;
		}
	}
</script>

<div class="min-h-screen bg-gray-950 flex items-center justify-center">
	<div class="w-full max-w-md px-4">
		<div class="text-center mb-8">
			<img src={$siteConfig.logo_path} alt={$siteConfig.site_name} class="h-28 w-auto mx-auto mb-4" />
			<h1 class="text-4xl font-bold text-white mb-2">{$siteConfig.site_name}</h1>
			<p class="text-gray-400 text-sm">{$siteConfig.site_description}</p>
		</div>

		<form
			onsubmit={(e) => { e.preventDefault(); login(); }}
			class="bg-gray-900 rounded-xl border border-gray-700 p-8 space-y-4"
		>
			{#if error}
				<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">
					{error}
				</div>
			{/if}

			<div>
				<label for="domain" class="block text-gray-400 text-xs mb-1.5 uppercase tracking-wide">도메인</label>
				<input
					id="domain"
					bind:value={domainName}
					type="text"
					class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
				/>
			</div>

			<div>
				<label for="username" class="block text-gray-400 text-xs mb-1.5 uppercase tracking-wide">사용자명</label>
				<input
					id="username"
					bind:value={username}
					type="text"
					required
					class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
				/>
			</div>

			<div>
				<label for="password" class="block text-gray-400 text-xs mb-1.5 uppercase tracking-wide">비밀번호</label>
				<input
					id="password"
					bind:value={password}
					type="password"
					required
					onkeydown={(e) => { if (e.key === 'Enter' && !loading) { e.preventDefault(); login(); } }}
					class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
				/>
			</div>

			<button
				type="submit"
				disabled={loading}
				class="w-full bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white font-medium rounded-lg py-2.5 text-sm transition-colors"
			>
				{loading ? '로그인 중...' : '로그인'}
			</button>

			{#if gitlabEnabled}
				<div class="relative my-2">
					<div class="absolute inset-0 flex items-center"><div class="w-full border-t border-gray-700"></div></div>
					<div class="relative flex justify-center text-xs"><span class="bg-gray-900 px-2 text-gray-500">또는</span></div>
				</div>
				<button
					type="button"
					onclick={loginWithGitlab}
					disabled={gitlabLoading}
					class="w-full flex items-center justify-center gap-2 bg-[#FC6D26] hover:bg-[#E24329] disabled:bg-gray-700 disabled:text-gray-500 text-white font-medium rounded-lg py-2.5 text-sm transition-colors"
				>
					<svg class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
						<path d="M22.65 14.39L12 22.13 1.35 14.39a.84.84 0 01-.3-.94l1.22-3.78 2.44-7.51A.42.42 0 014.93 2a.43.43 0 01.41.3l2.44 7.49h8.44l2.44-7.49a.42.42 0 01.41-.3.43.43 0 01.41.16l2.44 7.51L23 13.45a.84.84 0 01-.35.94z"/>
					</svg>
					{gitlabLoading ? '리다이렉트 중...' : 'GitLab으로 로그인'}
				</button>
			{/if}
		</form>
	</div>
</div>
