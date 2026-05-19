<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import ProjectQuotaPanel from '$lib/components/ProjectQuotaPanel.svelte';
	import type { Overview, VersionInfo, ProjectUsage } from '$lib/types/adminOverview';
	import KpiCardRow from '$lib/components/admin/overview/KpiCardRow.svelte';
	import ResourceDonutsCard from '$lib/components/admin/overview/ResourceDonutsCard.svelte';
	import ProjectUsageTable from '$lib/components/admin/overview/ProjectUsageTable.svelte';
	import ServiceCountCards from '$lib/components/admin/overview/ServiceCountCards.svelte';
	import VersionInfoPanel from '$lib/components/admin/overview/VersionInfoPanel.svelte';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import { StatTile, SectionHeader, Pill } from '$lib/components/ui';

	interface Notification {
		severity: string;
		message: string;
		target: string;
		href: string;
	}

	let overview = $state<Overview | null>(null);
	let overviewLoading = $state(true);
	let error = $state('');
	let projectUsage = $state<ProjectUsage[]>([]);
	let projectUsageLoading = $state(true);
	let versionInfo = $state<VersionInfo | null>(null);
	let versionOpen = $state(false);
	let selectedProject = $state<ProjectUsage | null>(null);
	let notifications = $state<Notification[]>([]);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	function loadProjectUsage() {
		projectUsageLoading = true;
		api.get<ProjectUsage[]>('/api/admin/overview/projects', token, projectId)
			.then(r => { projectUsage = r; })
			.catch(() => {})
			.finally(() => { projectUsageLoading = false; });
	}

	const ar = createAutoRefresh(
		() => { loadProjectUsage(); },
		{ storageKey: 'admin-overview', defaultActive: true, defaultInterval: 60, invokeOnMount: false }
	);

	onMount(() => {
		api.get<Overview>('/api/admin/overview', token, projectId)
			.then(r => { overview = r; })
			.catch((e) => {
				if (e instanceof ApiError && e.status === 403) { goto('/dashboard'); return; }
				error = e instanceof ApiError ? `조회 실패: ${e.message}` : '서버 오류';
			})
			.finally(() => { overviewLoading = false; });

		loadProjectUsage();

		api.get<VersionInfo>('/api/admin/version', token, projectId)
			.then(r => { versionInfo = r; })
			.catch(() => {});

		api.get<Notification[]>('/api/admin/notifications', token, projectId)
			.then(r => { notifications = r; })
			.catch(() => {});
	});
</script>

<div class="p-6 flex flex-col gap-5">
	<!-- 헤더 -->
	<div class="flex items-start justify-between gap-3">
		<div>
			<div class="text-[11px] text-gray-500 uppercase tracking-widest font-medium mb-1">ADMIN · 관리자</div>
			<h1 class="text-2xl font-bold text-white mb-1">관리자 개요</h1>
			<p class="text-xs" style="color: var(--color-ink-3);">클러스터 전반 · 자원 현황 · 실시간 알림</p>
		</div>
		{#if notifications.length > 0}
			{@const critCount = notifications.filter(n => n.severity === 'critical').length}
			{@const warnCount = notifications.filter(n => n.severity === 'warning').length}
			<div class="flex items-center gap-1.5 mt-1">
				{#if critCount > 0}
					<Pill tone="danger">{critCount} CRIT</Pill>
				{/if}
				{#if warnCount > 0}
					<Pill tone="warning">{warnCount} WARN</Pill>
				{/if}
			</div>
		{/if}
	</div>

	{#if notifications.length > 0}
		{@const critCount = notifications.filter(n => n.severity === 'critical').length}
		{@const warnCount = notifications.filter(n => n.severity === 'warning').length}
		<div class="bg-gray-900 border border-gray-800 rounded-2xl p-4 flex items-center gap-3 border-l-4"
			 style="border-left-color: var(--color-state-danger);">
			<span class="w-1.5 h-1.5 rounded-full animate-pulse shrink-0"
				  style="background: var(--color-state-danger);"></span>
			<span class="text-sm" style="color: var(--color-ink-1);">
				{#if critCount > 0}
					<span class="font-semibold" style="color: var(--color-state-danger);">{critCount} critical</span> ·
				{/if}
				{#if warnCount > 0}
					<span class="font-semibold" style="color: var(--color-state-warning);">{warnCount} warning</span> ·
				{/if}
				{notifications.length - critCount - warnCount} info —
				<a href="/admin/monitoring" class="underline" style="color: var(--admin-tone);">모니터링 상세 →</a>
			</span>
			<div class="ml-auto flex gap-1.5">
				{#each notifications.filter(n => n.severity === 'critical').slice(0, 1) as n}
					<Pill tone="danger">{n.severity.toUpperCase()}</Pill>
				{/each}
				{#if warnCount > 0}
					<Pill tone="warning">{warnCount} WARN</Pill>
				{/if}
			</div>
		</div>
	{/if}

	{#if error}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-xl px-4 py-3 text-sm">{error}</div>
	{/if}

	{#if overviewLoading}
		<div class="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
			{#each Array(3) as _}
				<div class="bg-gray-900 border border-gray-800 rounded-2xl p-[18px] animate-pulse h-[82px]"></div>
			{/each}
		</div>
		<div class="bg-gray-900 border border-gray-800 rounded-2xl p-5 animate-pulse h-[260px]"></div>
	{:else if overview}
		<KpiCardRow {overview} />
		<ResourceDonutsCard {overview} />

		<div class="grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-3.5">
			<ProjectUsageTable
				projects={projectUsage}
				loading={projectUsageLoading}
				onSelectProject={(p) => { selectedProject = p; }}
			/>
			<ServiceCountCards {overview} />
		</div>

		<!-- 퀵 링크 -->
		<div class="flex gap-3 flex-wrap text-sm">
			<a href="/admin/hypervisors" class="text-gray-500 hover:text-gray-200 transition-colors">하이퍼바이저 →</a>
			<a href="/admin/instances" class="text-gray-500 hover:text-gray-200 transition-colors">전체 인스턴스 →</a>
			<a href="/admin/containers" class="text-gray-500 hover:text-gray-200 transition-colors">전체 컨테이너 →</a>
			<a href="/admin/file-storage" class="text-gray-500 hover:text-gray-200 transition-colors">파일 스토리지 →</a>
			<a href="/admin/database-instances" class="text-gray-500 hover:text-gray-200 transition-colors">Database →</a>
			<a href="/admin/object-storage" class="text-gray-500 hover:text-gray-200 transition-colors">Object Storage →</a>
			<a href="/admin/topology" class="text-gray-500 hover:text-gray-200 transition-colors">전체 토폴로지 →</a>
			<a href="/admin/networks" class="text-gray-500 hover:text-gray-200 transition-colors">네트워크 →</a>
		</div>

		<VersionInfoPanel {versionInfo} bind:open={versionOpen} />
	{:else}
		<div class="text-gray-500 text-sm">개요를 불러올 수 없습니다</div>
	{/if}
</div>

{#if selectedProject}
	<ProjectQuotaPanel
		projectId={selectedProject.project_id}
		projectName={selectedProject.project_name}
		{token}
		authProjectId={projectId}
		onClose={() => { selectedProject = null; }}
		onUpdated={() => { loadProjectUsage(); }}
	/>
{/if}
