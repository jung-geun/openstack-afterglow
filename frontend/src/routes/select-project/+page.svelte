<script lang="ts">
	import { goto } from '$app/navigation';
	import { auth, clearAuth, setProject } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import type { Project } from '$lib/stores/auth';

	let projects = $state<Project[]>([]);
	let loading = $state(true);
	let error = $state('');

	async function load() {
		loading = true;
		error = '';
		try {
			projects = await api.get<Project[]>('/api/auth/projects/recent', $auth.token ?? undefined);
		} catch (e) {
			error = e instanceof ApiError ? e.message : '프로젝트 목록을 불러오지 못했습니다';
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		if ($auth.token) load();
	});

	function selectProject(proj: Project) {
		setProject(proj.id, proj.name);
		goto('/dashboard');
	}

	function logout() {
		if ($auth.token) {
			api.post('/api/auth/logout', {}, $auth.token).catch(() => {});
		}
		clearAuth();
		goto('/');
	}

	function formatRelativeTime(iso: string | null | undefined): string {
		if (!iso) return '-';
		const diff = Date.now() - new Date(iso).getTime();
		const minutes = Math.floor(diff / 60_000);
		if (minutes < 1) return '방금 전';
		if (minutes < 60) return `${minutes}분 전`;
		const hours = Math.floor(minutes / 60);
		if (hours < 24) return `${hours}시간 전`;
		const days = Math.floor(hours / 24);
		if (days < 30) return `${days}일 전`;
		const months = Math.floor(days / 30);
		if (months < 12) return `${months}개월 전`;
		return `${Math.floor(months / 12)}년 전`;
	}

	function orgLabel(domain_name: string | null | undefined): string {
		if (!domain_name || domain_name === 'Default') return 'No organization';
		return domain_name;
	}
</script>

<div class="min-h-screen bg-gray-950 text-white">
	<!-- 상단 알림 바 -->
	<div class="border-b border-gray-800 bg-[#0B1220]">
		<div class="max-w-6xl mx-auto px-6 py-3 flex items-center justify-between gap-4">
			<div class="flex items-center gap-2 text-sm text-gray-400">
				<svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
				</svg>
				<span>작업할 프로젝트를 선택해주세요.</span>
			</div>
			<button
				onclick={logout}
				class="text-sm text-gray-500 hover:text-white transition-colors"
			>
				로그아웃
			</button>
		</div>
	</div>

	<!-- 본문 -->
	<div class="max-w-6xl mx-auto px-6 py-10">
		<h1 class="text-lg font-semibold text-white mb-6">최근 프로젝트 선택</h1>

		{#if loading}
			<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
				{#each [1, 2, 3, 4, 5] as _}
					<div class="h-28 bg-gray-800 rounded-xl animate-pulse"></div>
				{/each}
			</div>
		{:else if error}
			<div class="text-red-400 text-sm">{error}</div>
		{:else if projects.length === 0}
			<div class="text-gray-500 text-sm text-center py-16">접근 가능한 프로젝트가 없습니다.</div>
		{:else}
			<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
				{#each projects as proj (proj.id)}
					<button
						onclick={() => selectProject(proj)}
						class="text-left border border-gray-700 rounded-xl p-5 bg-gray-900 hover:border-blue-500 hover:bg-gray-800 transition-all cursor-pointer"
					>
						<div class="font-medium text-white mb-3 truncate">{proj.name}</div>
						<div class="space-y-1 text-[13px] text-gray-400">
							<div class="flex gap-1.5">
								<span class="shrink-0">프로젝트 ID:</span>
								<span class="truncate font-mono text-gray-300">{proj.id}</span>
							</div>
							<div class="flex gap-1.5">
								<span class="shrink-0">조직:</span>
								<span class="truncate">{orgLabel(proj.domain_name)}</span>
							</div>
							<div class="flex gap-1.5">
								<span class="shrink-0">액세스 시기:</span>
								<span>{formatRelativeTime(proj.last_accessed_at)}</span>
							</div>
						</div>
					</button>
				{/each}
			</div>
		{/if}
	</div>
</div>
