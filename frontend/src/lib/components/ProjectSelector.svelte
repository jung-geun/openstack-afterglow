<script lang="ts">
	import { onMount } from 'svelte';
	import { auth, setAuth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSpinner from './LoadingSpinner.svelte';

	interface Project {
		id: string;
		name: string;
		description?: string;
	}

	let projects = $state<Project[]>([]);
	let loading = $state(true);
	let switching = $state(false);
	let error = $state('');
	let isOpen = $state(false);
	let dropdownRef: HTMLDivElement | null = $state(null);

	async function fetchProjects() {
		if (!$auth.token) return;
		loading = true;
		try {
			projects = await api.get<Project[]>('/api/auth/projects', $auth.token);
			error = '';
		} catch (e) {
			error = e instanceof ApiError ? e.message : '프로젝트 목록 조회 실패';
		} finally {
			loading = false;
		}
	}

	async function selectProject(project: Project) {
		if (!$auth.token || switching) return;
		if (project.id === $auth.projectId) { isOpen = false; return; }

		switching = true;
		try {
			const resp = await api.post<{
				token: string;
				refresh_token: string;
				expires_at: string;
				project_id: string;
				project_name: string;
				user_id: string;
				username: string;
				roles: string[];
				is_system_admin: boolean;
			}>('/api/auth/switch-project', { project_id: project.id }, $auth.token);

			setAuth({
				token: resp.token,
				refreshToken: resp.refresh_token,
				accessExpiresAt: resp.expires_at
					? Math.floor(new Date(resp.expires_at).getTime() / 1000)
					: null,
				projectId: resp.project_id,
				projectName: resp.project_name,
				roles: resp.roles ?? [],
				isSystemAdmin: !!resp.is_system_admin,
			});

			isOpen = false;

			// Default 네트워크 확인/생성 (fire-and-forget)
			api.post('/api/networks/ensure-default', {}, resp.token, resp.project_id).catch(() => {});
		} catch (e) {
			error = e instanceof ApiError ? `프로젝트 전환 실패: ${e.message}` : '프로젝트 전환 실패';
		} finally {
			switching = false;
		}
	}

	function handleClickOutside(event: MouseEvent) {
		if (dropdownRef && !dropdownRef.contains(event.target as Node)) {
			isOpen = false;
		}
	}

	onMount(() => {
		fetchProjects();
		document.addEventListener('click', handleClickOutside);
		return () => document.removeEventListener('click', handleClickOutside);
	});
</script>

<div class="relative" bind:this={dropdownRef}>
	<button
		onclick={() => { if (!loading && !switching) isOpen = !isOpen; }}
		disabled={loading || switching}
		class="flex items-center gap-2 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 disabled:bg-gray-800/50 rounded-lg text-sm transition-colors"
	>
		{#if loading || switching}
			<LoadingSpinner size="sm" color="gray" />
		{:else}
			<svg class="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-4 0H7m0 0H5m2 0v-2a2 2 0 012-2h2m4 0h2a2 2 0 012 2v2m-6-6a2 2 0 100-4 2 2 0 000 4z"></path>
			</svg>
		{/if}
		<span class="text-gray-300">{$auth.projectName || '프로젝트 선택'}</span>
		<svg class="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
			<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
		</svg>
	</button>

	{#if isOpen && !loading}
		<div class="fixed left-0 bottom-0 w-full sm:absolute sm:bottom-auto sm:top-full sm:mt-1 sm:left-0 sm:w-64 max-h-[50vh] sm:max-h-64 bg-gray-900 border border-gray-700 rounded-t-lg sm:rounded-lg shadow-xl z-50 overflow-hidden">
			{#if error}
				<div class="p-3 text-sm text-red-400">{error}</div>
			{:else if projects.length === 0}
				<div class="p-3 text-sm text-gray-500">접근 가능한 프로젝트가 없습니다</div>
			{:else}
				<div class="overflow-y-auto max-h-[calc(50vh-1rem)] sm:max-h-64">
					{#each projects as project}
						<button
							onclick={() => selectProject(project)}
							disabled={switching}
							class="w-full text-left px-3 py-2 hover:bg-gray-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed
								{project.id === $auth.projectId ? 'bg-blue-900/30 border-l-2 border-blue-500' : ''}"
						>
							<div class="text-sm font-medium text-white">{project.name}</div>
							{#if project.description}
								<div class="text-xs text-gray-500 truncate">{project.description}</div>
							{/if}
						</button>
					{/each}
				</div>
			{/if}
		</div>
	{/if}
</div>