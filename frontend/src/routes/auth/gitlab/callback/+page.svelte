<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { setAuth, setAvailableProjects } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';

	interface Project {
		id: string;
		name: string;
		description?: string;
	}

	let error = $state('');
	let loading = $state(true);

	onMount(async () => {
		const code = $page.url.searchParams.get('code');
		const state = $page.url.searchParams.get('state');

		if (!code || !state) {
			error = '잘못된 콜백 요청입니다. 다시 로그인해 주세요.';
			loading = false;
			return;
		}

		// 동일 code 재사용 방지 (HMR/remount/reload 시 onMount 재실행 대응)
		const guardKey = `gitlab-callback-consumed:${code}`;
		if (sessionStorage.getItem(guardKey)) {
			return;
		}
		sessionStorage.setItem(guardKey, '1');
		// URL에서 code/state를 즉시 제거하여 reload 시 재호출되지 않게 함
		try {
			history.replaceState(null, '', '/auth/gitlab/callback');
		} catch {
			/* noop */
		}

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
				is_system_admin?: boolean;
			}>('/api/auth/gitlab/callback', { code, state });

			// 프로젝트 목록 + 세션 설정 병렬 조회
			const [projectsResult, sessionInfoResult] = await Promise.allSettled([
				api.get<Project[]>('/api/auth/projects', data.token),
				api.get<{ timeout_seconds: number; warning_before_seconds: number }>(
					'/api/auth/session-info', data.token, data.project_id
				),
			]);
			const projects: Project[] =
				projectsResult.status === 'fulfilled' ? projectsResult.value : [];
			const sessionTimeoutSeconds =
				sessionInfoResult.status === 'fulfilled' ? sessionInfoResult.value.timeout_seconds : 3600;
			const sessionWarningBeforeSeconds =
				sessionInfoResult.status === 'fulfilled' ? sessionInfoResult.value.warning_before_seconds : 300;

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
				refreshToken: (data as { refresh_token?: string }).refresh_token ?? null,
				accessExpiresAt: data.expires_at
					? Math.floor(new Date(data.expires_at).getTime() / 1000)
					: null,
				userId: data.user_id,
				username: data.username,
				projectId: selectedProjectId,
				projectName: selectedProjectName,
				sessionTimeoutSeconds,
				sessionWarningBeforeSeconds,
				roles: data.roles ?? [],
				isSystemAdmin: data.is_system_admin ?? false,
			});
			setAvailableProjects(projects);
			goto('/dashboard');
		} catch (e) {
			error = e instanceof ApiError ? `인증 실패 (${e.status}): ${e.message}` : 'GitLab 인증에 실패했습니다';
			loading = false;
		}
	});
</script>

<div class="min-h-screen bg-gray-950 flex items-center justify-center">
	<div class="w-full max-w-md px-4 text-center">
		{#if loading}
			<div class="flex flex-col items-center gap-4">
				<svg class="w-10 h-10 text-[#FC6D26] animate-spin" fill="none" viewBox="0 0 24 24">
					<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
					<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path>
				</svg>
				<p class="text-gray-400 text-sm">GitLab 인증 처리 중...</p>
			</div>
		{:else if error}
			<div class="bg-gray-900 rounded-xl border border-gray-700 p-8 space-y-4">
				<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">
					{error}
				</div>
				<a href="/" class="block w-full text-center bg-gray-800 hover:bg-gray-700 text-gray-300 font-medium rounded-lg py-2.5 text-sm transition-colors">
					로그인 페이지로 돌아가기
				</a>
			</div>
		{/if}
	</div>
</div>
