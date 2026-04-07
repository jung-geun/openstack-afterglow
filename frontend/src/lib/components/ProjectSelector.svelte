<script lang="ts">
	import { onMount } from 'svelte';
	import { auth, setProject } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSpinner from './LoadingSpinner.svelte';

	interface Project {
		id: string;
		name: string;
		description?: string;
	}

	let projects = $state<Project[]>([]);
	let loading = $state(true);
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

	function selectProject(project: Project) {
		setProject(project.id, project.name);
		isOpen = false;
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
		onclick={() => { if (!loading) isOpen = !isOpen; }}
		disabled={loading}
		class="flex items-center gap-2 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 disabled:bg-gray-800/50 rounded-lg text-sm transition-colors"
	>
		{#if loading}
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
		<div class="absolute top-full left-0 mt-1 w-64 bg-gray-900 border border-gray-700 rounded-lg shadow-xl z-50 overflow-hidden">
			{#if error}
				<div class="p-3 text-sm text-red-400">{error}</div>
			{:else if projects.length === 0}
				<div class="p-3 text-sm text-gray-500">접근 가능한 프로젝트가 없습니다</div>
			{:else}
				<div class="max-h-64 overflow-y-auto">
					{#each projects as project}
						<button
							onclick={() => selectProject(project)}
							class="w-full text-left px-3 py-2 hover:bg-gray-800 transition-colors
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