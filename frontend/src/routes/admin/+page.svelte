<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import QuotaDonut from '$lib/components/QuotaDonut.svelte';
	import ProjectQuotaPanel from '$lib/components/ProjectQuotaPanel.svelte';
	import { formatNumber, formatStorage } from '$lib/utils/format';

	interface Overview {
		hypervisor_count: number;
		running_vms: number;
		gpu_instances: number;
		instance_stats?: { total: number; active: number; shutoff: number; error: number; other: number };
		vcpus: { total: number; allowed: number; used: number };
		ram_gb: { total: number; used: number };
		disk_gb: { total: number; used: number };
		containers_count: number;
		file_storage_count: number;
	}

	declare const __APP_VERSION__: string;

	interface VersionInfo {
		platform: { backend_version: string };
		runtime: { python_version: string; uptime_seconds: number };
		dependencies: Record<string, string | null>;
		git: { commit: string | null; tag: string | null; branch: string | null };
		config: { k3s_version: string };
	}

	interface ProjectUsage {
		project_id: string;
		project_name: string;
		cpu: { used: number; quota: number };
		ram_mb: { used: number; quota: number };
		instances: { used: number; quota: number };
		disk_gb: { used: number; quota: number };
		gpu_instances: number;
	}

	let overview = $state<Overview | null>(null);
	let overviewLoading = $state(true);
	let error = $state('');
	let projectUsage = $state<ProjectUsage[]>([]);
	let projectUsageLoading = $state(true);
	let versionInfo = $state<VersionInfo | null>(null);
	let versionOpen = $state(false);
	let selectedProject = $state<ProjectUsage | null>(null);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	function usageBar(used: number, quota: number): string {
		if (quota <= 0) return '0';
		const pct = Math.min(100, Math.round((used / quota) * 100));
		return `${pct}`;
	}

	function usageColor(used: number, quota: number): string {
		if (quota <= 0) return 'bg-gray-600';
		const pct = (used / quota) * 100;
		if (pct >= 100) return 'bg-red-500';
		if (pct >= 80) return 'bg-orange-500';
		return 'bg-blue-500';
	}

	function formatQuota(used: number, quota: number, unit = ''): string {
		const u = unit === 'GB' ? Math.round(used) : used;
		const q = quota === -1 ? '∞' : (unit === 'GB' ? Math.round(quota) : quota);
		return `${u}/${q}${unit ? ' ' + unit : ''}`;
	}

	function formatUptime(seconds: number): string {
		const d = Math.floor(seconds / 86400);
		const h = Math.floor((seconds % 86400) / 3600);
		const m = Math.floor((seconds % 3600) / 60);
		const parts = [];
		if (d > 0) parts.push(`${d}d`);
		if (h > 0) parts.push(`${h}h`);
		parts.push(`${m}m`);
		return parts.join(' ');
	}

	function loadProjectUsage() {
		projectUsageLoading = true;
		api.get<ProjectUsage[]>('/api/admin/overview/projects', token, projectId)
			.then(r => { projectUsage = r; })
			.catch(() => {})
			.finally(() => { projectUsageLoading = false; });
	}

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
	});
</script>

<div class="p-4 md:p-8 max-w-6xl">
	<div class="flex items-center justify-between mb-8">
		<h1 class="text-2xl font-bold text-white">관리자 개요</h1>
	</div>

	{#if error}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>
	{/if}

	{#if overviewLoading}
		<LoadingSkeleton variant="table" rows={5} />
	{:else if overview}
		<!-- 상단: 주요 지표 카드 -->
		<div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-6 flex items-center gap-5">
				<div class="w-12 h-12 rounded-xl bg-blue-600/20 flex items-center justify-center shrink-0">
					<svg class="w-6 h-6 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2"></path></svg>
				</div>
				<div>
					<div class="text-xs text-gray-500 uppercase tracking-wide mb-0.5">하이퍼바이저</div>
					<div class="text-3xl font-bold text-white">{formatNumber(overview.hypervisor_count)}</div>
					<a href="/admin/hypervisors" class="text-xs text-blue-400 hover:text-blue-300 mt-1 inline-block">상세 보기 →</a>
				</div>
			</div>
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-6 flex items-center gap-5">
				<div class="w-12 h-12 rounded-xl bg-green-600/20 flex items-center justify-center shrink-0">
					<svg class="w-6 h-6 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18"></path></svg>
				</div>
				<div>
					<div class="text-xs text-gray-500 uppercase tracking-wide mb-0.5">총 VM</div>
					<div class="text-3xl font-bold text-white">{formatNumber(overview.running_vms)}</div>
					{#if overview.instance_stats}
						<div class="flex flex-wrap gap-x-3 gap-y-0.5 mt-1">
							<span class="text-xs text-green-400">● Active {overview.instance_stats.active}</span>
							<span class="text-xs text-red-400">● Error {overview.instance_stats.error}</span>
							<span class="text-xs text-gray-400">● Shutoff {overview.instance_stats.shutoff}</span>
							{#if overview.instance_stats.other > 0}
								<span class="text-xs text-yellow-400">● Others {overview.instance_stats.other}</span>
							{/if}
						</div>
					{/if}
					<a href="/admin/instances" class="text-xs text-blue-400 hover:text-blue-300 mt-1 inline-block">전체 보기 →</a>
				</div>
			</div>
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-6 flex items-center gap-5">
				<div class="w-12 h-12 rounded-xl bg-purple-600/20 flex items-center justify-center shrink-0">
					<svg class="w-6 h-6 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"></path></svg>
				</div>
				<div>
					<div class="text-xs text-gray-500 uppercase tracking-wide mb-0.5">GPU VM</div>
					<div class="text-3xl font-bold {overview.gpu_instances > 0 ? 'text-purple-300' : 'text-white'}">{formatNumber(overview.gpu_instances)}</div>
					<div class="text-xs text-gray-600 mt-1">GPU 가속 인스턴스</div>
				</div>
			</div>
		</div>

		<!-- 중단: 리소스 사용률 도넛 차트 -->
		<div class="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-6">
			<h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-6">클러스터 리소스 사용률</h2>
			<div class="grid grid-cols-1 sm:grid-cols-3 gap-8">
				<div class="flex flex-col items-center gap-3">
					<QuotaDonut
						label="CPU 코어"
						used={overview.vcpus.used}
						limit={overview.vcpus.allowed}
						size="lg"
					/>
					<div class="text-center">
						<div class="text-xl font-bold text-white">{formatNumber(overview.vcpus.used)} <span class="text-gray-500 text-sm font-normal">/ {formatNumber(overview.vcpus.allowed)}</span></div>
						<div class="text-xs text-gray-500">vCPU</div>
					</div>
				</div>
				<div class="flex flex-col items-center gap-3">
					<QuotaDonut
						label="메모리"
						used={overview.ram_gb.used}
						limit={overview.ram_gb.total}
						unit="GB"
						size="lg"
					/>
					<div class="text-center">
						<div class="text-xl font-bold text-white">{formatNumber(overview.ram_gb.used)} <span class="text-gray-500 text-sm font-normal">/ {formatNumber(overview.ram_gb.total)} GB</span></div>
						<div class="text-xs text-gray-500">RAM</div>
					</div>
				</div>
				<div class="flex flex-col items-center gap-3">
					<QuotaDonut
						label="블록 스토리지"
						used={overview.disk_gb.used}
						limit={overview.disk_gb.total}
						unit="GB"
						size="lg"
					/>
					<div class="text-center">
						<div class="text-xl font-bold text-white">{formatStorage(overview.disk_gb.used)} <span class="text-gray-500 text-sm font-normal">/ {formatStorage(overview.disk_gb.total)}</span></div>
						<div class="text-xs text-gray-500">Disk</div>
					</div>
				</div>
			</div>
		</div>

		<!-- 프로젝트별 리소스 사용량 -->
		<div class="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-6">
			<h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-4">프로젝트별 리소스</h2>
			{#if projectUsageLoading}
				<div class="text-gray-500 text-sm">불러오는 중...</div>
			{:else if projectUsage.length > 0}
				<div class="overflow-x-auto">
					<table class="w-full text-sm">
						<thead>
							<tr class="text-left text-gray-500 border-b border-gray-800">
								<th class="pb-2 pr-4 font-medium">프로젝트</th>
								<th class="pb-2 pr-4 font-medium text-right">인스턴스</th>
								<th class="pb-2 pr-4 font-medium">CPU</th>
								<th class="pb-2 pr-4 font-medium">RAM</th>
								<th class="pb-2 pr-4 font-medium">Disk</th>
								<th class="pb-2 font-medium text-right">GPU</th>
							</tr>
						</thead>
						<tbody>
							{#each projectUsage.filter(p => p.instances.used > 0 || p.cpu.used > 0 || p.disk_gb.used > 0) as p}
								<tr
									class="border-b border-gray-800/50 hover:bg-gray-800/30 cursor-pointer"
									onclick={() => { selectedProject = p; }}
									role="button"
									tabindex="0"
									onkeydown={(e) => { if (e.key === 'Enter') selectedProject = p; }}
								>
									<td class="py-2 pr-4">
										<span class="text-white font-medium">{p.project_name}</span>
										<span class="text-gray-600 text-xs ml-1">{p.project_id.slice(0, 8)}</span>
									</td>
									<td class="py-2 pr-4 text-right text-gray-300 font-mono text-xs">
										{formatQuota(p.instances.used, p.instances.quota)}
									</td>
									<td class="py-2 pr-4">
										<div class="flex items-center gap-2">
											<div class="w-16 h-1.5 bg-gray-700 rounded-full overflow-hidden">
												<div class="h-full rounded-full {usageColor(p.cpu.used, p.cpu.quota)}" style="width: {usageBar(p.cpu.used, p.cpu.quota)}%"></div>
											</div>
											<span class="text-gray-300 font-mono text-xs whitespace-nowrap">{formatQuota(p.cpu.used, p.cpu.quota)}</span>
										</div>
									</td>
									<td class="py-2 pr-4">
										<div class="flex items-center gap-2">
											<div class="w-16 h-1.5 bg-gray-700 rounded-full overflow-hidden">
												<div class="h-full rounded-full {usageColor(p.ram_mb.used, p.ram_mb.quota)}" style="width: {usageBar(p.ram_mb.used, p.ram_mb.quota)}%"></div>
											</div>
											<span class="text-gray-300 font-mono text-xs whitespace-nowrap">{Math.round(p.ram_mb.used/1024)}/{p.ram_mb.quota === -1 ? '∞' : Math.round(p.ram_mb.quota/1024)} GB</span>
										</div>
									</td>
									<td class="py-2 pr-4">
										<div class="flex items-center gap-2">
											<div class="w-16 h-1.5 bg-gray-700 rounded-full overflow-hidden">
												<div class="h-full rounded-full {usageColor(p.disk_gb.used, p.disk_gb.quota)}" style="width: {usageBar(p.disk_gb.used, p.disk_gb.quota)}%"></div>
											</div>
											<span class="text-gray-300 font-mono text-xs whitespace-nowrap">{formatQuota(p.disk_gb.used, p.disk_gb.quota, 'GB')}</span>
										</div>
									</td>
									<td class="py-2 text-right">
										{#if p.gpu_instances > 0}
											<span class="text-purple-400 font-mono text-xs">{p.gpu_instances}</span>
										{:else}
											<span class="text-gray-600 text-xs">-</span>
										{/if}
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{:else}
				<div class="text-gray-500 text-sm">데이터가 없습니다</div>
			{/if}
		</div>

		<!-- 하단: 서비스 카운트 + 퀵 링크 -->
		<div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
			<a href="/admin/containers" class="bg-gray-900 border border-gray-800 rounded-xl p-6 flex items-center gap-5 hover:border-gray-600 transition-colors">
				<div class="w-12 h-12 rounded-xl bg-orange-600/20 flex items-center justify-center shrink-0">
					<svg class="w-6 h-6 text-orange-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"></path></svg>
				</div>
				<div>
					<div class="text-xs text-gray-500 uppercase tracking-wide mb-0.5">컨테이너</div>
					<div class="text-3xl font-bold text-white">{formatNumber(overview.containers_count ?? 0)}</div>
				</div>
			</a>
			<a href="/admin/file-storage" class="bg-gray-900 border border-gray-800 rounded-xl p-6 flex items-center gap-5 hover:border-gray-600 transition-colors">
				<div class="w-12 h-12 rounded-xl bg-yellow-600/20 flex items-center justify-center shrink-0">
					<svg class="w-6 h-6 text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"></path></svg>
				</div>
				<div>
					<div class="text-xs text-gray-500 uppercase tracking-wide mb-0.5">파일 스토리지</div>
					<div class="text-3xl font-bold text-white">{formatNumber(overview.file_storage_count ?? 0)}</div>
				</div>
			</a>
		</div>

		<!-- 퀵 링크 -->
		<div class="flex gap-3 flex-wrap">
			<a href="/admin/hypervisors" class="text-sm text-blue-400 hover:text-blue-300 transition-colors">하이퍼바이저 →</a>
			<a href="/admin/instances" class="text-sm text-blue-400 hover:text-blue-300 transition-colors">전체 인스턴스 →</a>
			<a href="/admin/containers" class="text-sm text-blue-400 hover:text-blue-300 transition-colors">전체 컨테이너 →</a>
			<a href="/admin/file-storage" class="text-sm text-blue-400 hover:text-blue-300 transition-colors">파일 스토리지 →</a>
			<a href="/admin/topology" class="text-sm text-blue-400 hover:text-blue-300 transition-colors">전체 토폴로지 →</a>
			<a href="/admin/networks" class="text-sm text-blue-400 hover:text-blue-300 transition-colors">네트워크 →</a>
		</div>

		<!-- 시스템 버전 정보 (접이식) -->
		<button
			class="mt-6 flex items-center gap-1.5 text-sm text-gray-600 hover:text-gray-400 transition-colors"
			onclick={() => versionOpen = !versionOpen}
		>
			<svg class="w-3.5 h-3.5 transition-transform {versionOpen ? 'rotate-90' : ''}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
			</svg>
			시스템 버전 정보
		</button>
		{#if versionOpen && versionInfo}
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-6 mt-2">
				<div class="grid grid-cols-1 sm:grid-cols-2 gap-x-12 gap-y-1">
					<!-- 플랫폼 -->
					<div class="col-span-full mb-2">
						<span class="text-xs font-semibold text-gray-500 uppercase tracking-wide">플랫폼</span>
					</div>
					<div class="flex justify-between py-1 border-b border-gray-800/50">
						<span class="text-xs text-gray-500">백엔드 버전</span>
						<span class="text-xs text-gray-300 font-mono">{versionInfo.platform.backend_version}</span>
					</div>
					<div class="flex justify-between py-1 border-b border-gray-800/50">
						<span class="text-xs text-gray-500">프론트엔드 버전</span>
						<span class="text-xs text-gray-300 font-mono">{__APP_VERSION__}</span>
					</div>
					<!-- 런타임 -->
					<div class="col-span-full mt-3 mb-2">
						<span class="text-xs font-semibold text-gray-500 uppercase tracking-wide">런타임</span>
					</div>
					<div class="flex justify-between py-1 border-b border-gray-800/50">
						<span class="text-xs text-gray-500">Python</span>
						<span class="text-xs text-gray-300 font-mono">{versionInfo.runtime.python_version}</span>
					</div>
					<div class="flex justify-between py-1 border-b border-gray-800/50">
						<span class="text-xs text-gray-500">업타임</span>
						<span class="text-xs text-gray-300 font-mono">{formatUptime(versionInfo.runtime.uptime_seconds)}</span>
					</div>
					<!-- 의존성 -->
					<div class="col-span-full mt-3 mb-2">
						<span class="text-xs font-semibold text-gray-500 uppercase tracking-wide">의존성</span>
					</div>
					{#each Object.entries(versionInfo.dependencies) as [pkg, ver]}
						<div class="flex justify-between py-1 border-b border-gray-800/50">
							<span class="text-xs text-gray-500">{pkg}</span>
							<span class="text-xs text-gray-300 font-mono">{ver ?? '-'}</span>
						</div>
					{/each}
					<!-- Git -->
					{#if versionInfo.git.commit}
						<div class="col-span-full mt-3 mb-2">
							<span class="text-xs font-semibold text-gray-500 uppercase tracking-wide">Git</span>
						</div>
						<div class="flex justify-between py-1 border-b border-gray-800/50">
							<span class="text-xs text-gray-500">커밋</span>
							<span class="text-xs text-gray-300 font-mono">{versionInfo.git.commit}</span>
						</div>
						{#if versionInfo.git.tag}
							<div class="flex justify-between py-1 border-b border-gray-800/50">
								<span class="text-xs text-gray-500">태그</span>
								<span class="text-xs text-gray-300 font-mono">{versionInfo.git.tag}</span>
							</div>
						{/if}
						{#if versionInfo.git.branch}
							<div class="flex justify-between py-1 border-b border-gray-800/50">
								<span class="text-xs text-gray-500">브랜치</span>
								<span class="text-xs text-gray-300 font-mono">{versionInfo.git.branch}</span>
							</div>
						{/if}
					{/if}
					<!-- 설정 -->
					<div class="col-span-full mt-3 mb-2">
						<span class="text-xs font-semibold text-gray-500 uppercase tracking-wide">설정</span>
					</div>
					<div class="flex justify-between py-1 border-b border-gray-800/50">
						<span class="text-xs text-gray-500">k3s 버전</span>
						<span class="text-xs text-gray-300 font-mono">{versionInfo.config.k3s_version}</span>
					</div>
				</div>
			</div>
		{/if}
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
