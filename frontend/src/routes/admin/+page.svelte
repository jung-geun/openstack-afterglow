<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
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
		database_instances_count: number;
		object_storage_containers_count: number;
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

<div class="p-6 flex flex-col gap-5">
	<!-- 헤더 -->
	<div>
		<div class="text-[11px] text-gray-500 uppercase tracking-widest font-medium mb-1">ADMIN · 관리자</div>
		<h1 class="text-2xl font-bold text-white mb-1">관리자 개요</h1>
	</div>

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
		<!-- 상단: 주요 지표 카드 -->
		<div class="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
			<!-- 하이퍼바이저 -->
			<div class="bg-gray-900 border border-gray-800 rounded-2xl p-[18px] flex items-center gap-3.5">
				<div class="w-10 h-10 rounded-[10px] shrink-0 border flex items-center justify-center bg-blue-500/15 border-blue-500/30 text-blue-400">
					<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2"/></svg>
				</div>
				<div class="flex-1 min-w-0">
					<div class="text-[11px] uppercase tracking-wider font-medium text-gray-500">하이퍼바이저</div>
					<div class="flex items-baseline gap-2 mt-0.5">
						<div class="text-[28px] font-bold text-white leading-none">{formatNumber(overview.hypervisor_count)}</div>
						<a href="/admin/hypervisors" class="ml-auto text-[11px] text-blue-400 hover:text-blue-300 transition-colors">상세 →</a>
					</div>
				</div>
			</div>

			<!-- 총 VM -->
			<div class="bg-gray-900 border border-gray-800 rounded-2xl p-[18px] flex items-center gap-3.5">
				<div class="w-10 h-10 rounded-[10px] shrink-0 border flex items-center justify-center bg-emerald-500/15 border-emerald-500/30 text-emerald-400">
					<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18"/></svg>
				</div>
				<div class="flex-1 min-w-0">
					<div class="text-[11px] uppercase tracking-wider font-medium text-gray-500">총 VM</div>
					<div class="flex items-baseline gap-2 mt-0.5 flex-wrap">
						<div class="text-[28px] font-bold text-white leading-none">{formatNumber(overview.running_vms)}</div>
						{#if overview.instance_stats}
							<div class="flex gap-2 text-[11px] ml-auto flex-wrap">
								<span class="text-emerald-400">● {overview.instance_stats.active}</span>
								<span class="text-red-400">● {overview.instance_stats.error} err</span>
							</div>
						{/if}
					</div>
					<a href="/admin/instances" class="text-[11px] text-blue-400 hover:text-blue-300 transition-colors">전체 보기 →</a>
				</div>
			</div>

			<!-- GPU VM -->
			<div class="bg-gray-900 border border-gray-800 rounded-2xl p-[18px] flex items-center gap-3.5">
				<div class="w-10 h-10 rounded-[10px] shrink-0 border flex items-center justify-center bg-violet-500/15 border-violet-500/30 text-violet-400">
					<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg>
				</div>
				<div class="flex-1 min-w-0">
					<div class="text-[11px] uppercase tracking-wider font-medium text-gray-500">GPU VM</div>
					<div class="flex items-baseline gap-2 mt-0.5">
						<div class="text-[28px] font-bold {overview.gpu_instances > 0 ? 'text-violet-300' : 'text-white'} leading-none">{formatNumber(overview.gpu_instances)}</div>
						<div class="text-gray-500 text-xs">인스턴스</div>
					</div>
				</div>
			</div>
		</div>

		<!-- 클러스터 리소스 사용률 (도넛 차트) -->
		<div class="bg-gray-900 border border-gray-800 rounded-2xl p-5">
			<div class="text-white text-[15px] font-semibold mb-5">클러스터 리소스 사용률</div>
			<div class="grid grid-cols-1 sm:grid-cols-3 gap-8">
				<div class="flex flex-col items-center gap-3">
					<QuotaDonut label="CPU 코어" used={overview.vcpus.used} limit={overview.vcpus.allowed} size="lg" />
					<div class="text-center">
						<div class="text-xl font-bold text-white">{formatNumber(overview.vcpus.used)} <span class="text-gray-500 text-sm font-normal">/ {formatNumber(overview.vcpus.allowed)}</span></div>
						<div class="text-xs text-gray-500">vCPU</div>
					</div>
				</div>
				<div class="flex flex-col items-center gap-3">
					<QuotaDonut label="메모리" used={overview.ram_gb.used} limit={overview.ram_gb.total} unit="GB" size="lg" />
					<div class="text-center">
						<div class="text-xl font-bold text-white">{formatNumber(overview.ram_gb.used)} <span class="text-gray-500 text-sm font-normal">/ {formatNumber(overview.ram_gb.total)} GB</span></div>
						<div class="text-xs text-gray-500">RAM</div>
					</div>
				</div>
				<div class="flex flex-col items-center gap-3">
					<QuotaDonut label="블록 스토리지" used={overview.disk_gb.used} limit={overview.disk_gb.total} unit="GB" size="lg" />
					<div class="text-center">
						<div class="text-xl font-bold text-white">{formatStorage(overview.disk_gb.used)} <span class="text-gray-500 text-sm font-normal">/ {formatStorage(overview.disk_gb.total)}</span></div>
						<div class="text-xs text-gray-500">Disk</div>
					</div>
				</div>
			</div>
		</div>

		<!-- 2-컬럼: 프로젝트 리소스 + 서비스 카운트 -->
		<div class="grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-3.5">
			<!-- 프로젝트별 리소스 -->
			<div class="bg-gray-900 border border-gray-800 rounded-2xl p-5">
				<div class="text-white text-[15px] font-semibold mb-3.5">프로젝트별 리소스</div>
				{#if projectUsageLoading}
					<div class="space-y-2">
						{#each Array(4) as _}
							<div class="h-9 bg-gray-800 rounded animate-pulse"></div>
						{/each}
					</div>
				{:else if projectUsage.length > 0}
					<!-- 테이블 헤더 -->
					<div class="grid grid-cols-[2fr_80px_1fr_1fr_1fr_60px] px-3.5 py-2 bg-[#0B1220] rounded-t-[10px] border border-gray-800 border-b-0 text-[11px] uppercase tracking-wider text-gray-500 font-medium">
						<div>프로젝트</div><div class="text-right">VM</div><div>CPU</div><div>RAM</div><div>Disk</div><div class="text-right">GPU</div>
					</div>
					<div class="border border-gray-800 rounded-b-[10px] overflow-hidden">
						{#each projectUsage.filter(p => p.instances.used > 0 || p.cpu.used > 0 || p.disk_gb.used > 0) as p, i}
							<button
								class="w-full grid grid-cols-[2fr_80px_1fr_1fr_1fr_60px] px-3.5 py-2.5 text-[13px] items-center hover:bg-gray-800/30 transition-colors text-left {i < projectUsage.filter(p => p.instances.used > 0 || p.cpu.used > 0 || p.disk_gb.used > 0).length - 1 ? 'border-b border-gray-800' : ''}"
								onclick={() => { selectedProject = p; }}
							>
								<div>
									<span class="text-white font-medium">{p.project_name}</span>
									<span class="text-gray-600 text-xs ml-1">{p.project_id.slice(0, 8)}</span>
								</div>
								<div class="text-right text-gray-300 font-mono text-xs">{formatQuota(p.instances.used, p.instances.quota)}</div>
								<div class="flex items-center gap-1.5">
									<div class="w-12 h-1.5 bg-gray-700 rounded-full overflow-hidden">
										<div class="h-full rounded-full {usageColor(p.cpu.used, p.cpu.quota)}" style="width: {usageBar(p.cpu.used, p.cpu.quota)}%"></div>
									</div>
									<span class="text-gray-400 font-mono text-[11px]">{p.cpu.used}</span>
								</div>
								<div class="flex items-center gap-1.5">
									<div class="w-12 h-1.5 bg-gray-700 rounded-full overflow-hidden">
										<div class="h-full rounded-full {usageColor(p.ram_mb.used, p.ram_mb.quota)}" style="width: {usageBar(p.ram_mb.used, p.ram_mb.quota)}%"></div>
									</div>
									<span class="text-gray-400 font-mono text-[11px]">{Math.round(p.ram_mb.used/1024)}G</span>
								</div>
								<div class="flex items-center gap-1.5">
									<div class="w-12 h-1.5 bg-gray-700 rounded-full overflow-hidden">
										<div class="h-full rounded-full {usageColor(p.disk_gb.used, p.disk_gb.quota)}" style="width: {usageBar(p.disk_gb.used, p.disk_gb.quota)}%"></div>
									</div>
									<span class="text-gray-400 font-mono text-[11px]">{Math.round(p.disk_gb.used)}G</span>
								</div>
								<div class="text-right">
									{#if p.gpu_instances > 0}
										<span class="text-violet-400 font-mono text-xs">{p.gpu_instances}</span>
									{:else}
										<span class="text-gray-700 text-xs">—</span>
									{/if}
								</div>
							</button>
						{/each}
					</div>
				{:else}
					<div class="text-gray-600 text-sm py-6 text-center">데이터가 없습니다</div>
				{/if}
			</div>

			<!-- 서비스 카운트 -->
			<div class="flex flex-col gap-3.5">
				<a href="/admin/containers" class="bg-gray-900 border border-gray-800 rounded-2xl p-[18px] flex items-center gap-3.5 hover:border-gray-700 transition-colors">
					<div class="w-10 h-10 rounded-[10px] shrink-0 border flex items-center justify-center bg-amber-500/15 border-amber-500/30 text-amber-400">
						<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/></svg>
					</div>
					<div>
						<div class="text-[11px] uppercase tracking-wider font-medium text-gray-500">컨테이너</div>
						<div class="text-[28px] font-bold text-white leading-none">{formatNumber(overview.containers_count ?? 0)}</div>
					</div>
				</a>
				<a href="/admin/file-storage" class="bg-gray-900 border border-gray-800 rounded-2xl p-[18px] flex items-center gap-3.5 hover:border-gray-700 transition-colors">
					<div class="w-10 h-10 rounded-[10px] shrink-0 border flex items-center justify-center bg-teal-500/15 border-teal-500/30 text-teal-400">
						<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"/></svg>
					</div>
					<div>
						<div class="text-[11px] uppercase tracking-wider font-medium text-gray-500">파일 스토리지</div>
						<div class="text-[28px] font-bold text-white leading-none">{formatNumber(overview.file_storage_count ?? 0)}</div>
					</div>
				</a>
				<a href="/admin/database-instances" class="bg-gray-900 border border-gray-800 rounded-2xl p-[18px] flex items-center gap-3.5 hover:border-gray-700 transition-colors">
					<div class="w-10 h-10 rounded-[10px] shrink-0 border flex items-center justify-center bg-cyan-500/15 border-cyan-500/30 text-cyan-400">
						<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7c0-1.657 3.582-3 8-3s8 1.343 8 3M4 7v5c0 1.657 3.582 3 8 3s8-1.343 8-3V7M4 7c0 1.657 3.582 3 8 3s8-1.343 8-3M4 12v5c0 1.657 3.582 3 8 3s8-1.343 8-3v-5"/></svg>
					</div>
					<div>
						<div class="text-[11px] uppercase tracking-wider font-medium text-gray-500">Database</div>
						<div class="text-[28px] font-bold text-white leading-none">{formatNumber(overview.database_instances_count ?? 0)}</div>
					</div>
				</a>
				<a href="/admin/object-storage" class="bg-gray-900 border border-gray-800 rounded-2xl p-[18px] flex items-center gap-3.5 hover:border-gray-700 transition-colors">
					<div class="w-10 h-10 rounded-[10px] shrink-0 border flex items-center justify-center bg-indigo-500/15 border-indigo-500/30 text-indigo-400">
						<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 15a4 4 0 004 4h9a5 5 0 10-.1-9.999 5.002 5.002 0 10-9.78 2.096A4.001 4.001 0 003 15z"/></svg>
					</div>
					<div>
						<div class="text-[11px] uppercase tracking-wider font-medium text-gray-500">Object Storage</div>
						<div class="text-[28px] font-bold text-white leading-none">{formatNumber(overview.object_storage_containers_count ?? 0)}</div>
					</div>
				</a>
			</div>
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

		<!-- 시스템 버전 정보 (접이식) -->
		<div>
			<button
				class="flex items-center gap-1.5 text-sm text-gray-600 hover:text-gray-400 transition-colors"
				onclick={() => versionOpen = !versionOpen}
			>
				<svg class="w-3.5 h-3.5 transition-transform {versionOpen ? 'rotate-90' : ''}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
				</svg>
				시스템 버전 정보
			</button>
			{#if versionOpen && versionInfo}
				<div class="bg-gray-900 border border-gray-800 rounded-2xl p-5 mt-2">
					<div class="grid grid-cols-1 sm:grid-cols-2 gap-x-12 gap-y-1">
						<div class="col-span-full mb-2">
							<span class="text-[11px] font-semibold text-gray-500 uppercase tracking-wider">플랫폼</span>
						</div>
						<div class="flex justify-between py-1 border-b border-gray-800/50">
							<span class="text-xs text-gray-500">백엔드 버전</span>
							<span class="text-xs text-gray-300 font-mono">{versionInfo.platform.backend_version}</span>
						</div>
						<div class="flex justify-between py-1 border-b border-gray-800/50">
							<span class="text-xs text-gray-500">프론트엔드 버전</span>
							<span class="text-xs text-gray-300 font-mono">{__APP_VERSION__}</span>
						</div>
						<div class="col-span-full mt-3 mb-2">
							<span class="text-[11px] font-semibold text-gray-500 uppercase tracking-wider">런타임</span>
						</div>
						<div class="flex justify-between py-1 border-b border-gray-800/50">
							<span class="text-xs text-gray-500">Python</span>
							<span class="text-xs text-gray-300 font-mono">{versionInfo.runtime.python_version}</span>
						</div>
						<div class="flex justify-between py-1 border-b border-gray-800/50">
							<span class="text-xs text-gray-500">업타임</span>
							<span class="text-xs text-gray-300 font-mono">{formatUptime(versionInfo.runtime.uptime_seconds)}</span>
						</div>
						<div class="col-span-full mt-3 mb-2">
							<span class="text-[11px] font-semibold text-gray-500 uppercase tracking-wider">의존성</span>
						</div>
						{#each Object.entries(versionInfo.dependencies) as [pkg, ver]}
							<div class="flex justify-between py-1 border-b border-gray-800/50">
								<span class="text-xs text-gray-500">{pkg}</span>
								<span class="text-xs text-gray-300 font-mono">{ver ?? '-'}</span>
							</div>
						{/each}
						{#if versionInfo.git.commit}
							<div class="col-span-full mt-3 mb-2">
								<span class="text-[11px] font-semibold text-gray-500 uppercase tracking-wider">Git</span>
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
						<div class="col-span-full mt-3 mb-2">
							<span class="text-[11px] font-semibold text-gray-500 uppercase tracking-wider">설정</span>
						</div>
						<div class="flex justify-between py-1 border-b border-gray-800/50">
							<span class="text-xs text-gray-500">k3s 버전</span>
							<span class="text-xs text-gray-300 font-mono">{versionInfo.config.k3s_version}</span>
						</div>
					</div>
				</div>
			{/if}
		</div>
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
