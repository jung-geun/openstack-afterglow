<script lang="ts">
	import { goto } from '$app/navigation';
	import { setAuth, setAvailableProjects, isLoggedIn } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';

	interface Project {
		id: string;
		name: string;
		description?: string;
	}

	let username = $state('');
	let password = $state('');
	let projectName = $state('');
	let error = $state('');
	let loading = $state(false);

	$effect(() => {
		if ($isLoggedIn) goto('/dashboard');
	});

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
			}>('/api/auth/login', { username, password, project_name: projectName });

			// 프로젝트 목록 조회
			let projects: Project[] = [];
			try {
				projects = await api.get<Project[]>('/api/auth/projects', data.token);
			} catch {
				// 프로젝트 목록 조회 실패 시 무시
			}

			setAuth({
				token: data.token,
				userId: data.user_id,
				username: data.username,
				projectId: data.project_id,
				projectName: data.project_name,
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
			<h1 class="text-4xl font-bold text-white mb-2">Union</h1>
			<p class="text-gray-400 text-sm">OpenStack VM + OverlayFS 배포 플랫폼</p>
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
					class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
				/>
			</div>

			<div>
				<label for="project" class="block text-gray-400 text-xs mb-1.5 uppercase tracking-wide">프로젝트 (선택)</label>
				<input
					id="project"
					bind:value={projectName}
					type="text"
					placeholder="기본 프로젝트 사용"
					class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2.5 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-blue-500 transition-colors"
				/>
			</div>

			<button
				type="submit"
				disabled={loading}
				class="w-full bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white font-medium rounded-lg py-2.5 text-sm transition-colors"
			>
				{loading ? '로그인 중...' : '로그인'}
			</button>
		</form>
	</div>
</div>
