<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { untrack } from 'svelte';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import RefreshButton from '$lib/components/RefreshButton.svelte';
	import AutoRefreshToggle from '$lib/components/AutoRefreshToggle.svelte';

	interface InstanceItem {
		id: string;
		name: string;
		status: string;
		flavor_name: string;
		created_at: string;
	}

	interface VolumeItem {
		id: string;
		name: string;
		status: string;
		size: number;
		volume_type: string;
		created_at: string;
	}

	interface ProjectData {
		project_id: string;
		project_name: string;
		instances: InstanceItem[];
		volumes: VolumeItem[];
		instance_count: number;
		volume_count: number;
		storage_gb: number;
		vcpus: number;
		ram_mb: number;
		network_count: number;
		fip_count: number;
		error?: boolean;
	}

	interface UserDashboardSummary {
		current_project_id: string;
		projects: ProjectData[];
		totals: {
			instances: number;
			volumes: number;
			storage_gb: number;
			vcpus: number;
			ram_mb: number;
			networks: number;
			floating_ips: number;
		};
	}

	let data = $state<UserDashboardSummary | null>(null);
	let initialLoading = $state(true);
	let refreshing = $state(false);
	let error = $state('');
	let autoRefresh = $state(false);
	let expandedProject = $state<string | null>(null);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function load(opts?: { refresh?: boolean }) {
		error = '';
		try {
			const result = await api.get<UserDashboardSummary>('/api/user-dashboard/summary', token, projectId, opts);
			data = result;
		} catch (e) {
			error = e instanceof ApiError ? e.message : '데이터를 불러올 수 없습니다';
		} finally {
			initialLoading = false;
		}
	}

	async function forceRefresh() {
		refreshing = true;
		try {
			await load({ refresh: true });
		} finally {
			refreshing = false;
		}
	}

	function toggleProject(id: string) {
		expandedProject = expandedProject === id ? null : id;
	}

	function statusColor(status: string) {
		switch (status?.toUpperCase()) {
			case 'ACTIVE': return 'text-green-400';
			case 'SHUTOFF': return 'text-gray-400';
			case 'ERROR': return 'text-red-400';
			case 'AVAILABLE': return 'text-green-400';
			case 'IN-USE': return 'text-blue-400';
			default: return 'text-yellow-400';
		}
	}

	function formatRam(mb: number): string {
		if (mb >= 1024) return `${(mb / 1024).toFixed(1)} GB`;
		return `${mb} MB`;
	}

	$effect(() => {
		const pid = $auth.projectId;
		if (!pid) return;
		untrack(() => { load(); });
	});

	$effect(() => {
		if (!$auth.projectId || !autoRefresh) return;
		const interval = setInterval(() => untrack(() => { load(); }), 30000);
		return () => clearInterval(interval);
	});
</script>

<div class="p-4 md:p-8 max-w-6xl">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-white">내 리소스</h1>
		<div class="flex items-center gap-2">
			<AutoRefreshToggle bind:active={autoRefresh} intervalSeconds={30} />
			<RefreshButton {refreshing} onclick={forceRefresh} />
		</div>
	</div>

	{#if error}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>
	{/if}

	{#if initialLoading}
		<LoadingSkeleton variant="table" rows={6} />
	{:else if data}
		<!-- 통합 요약 카드 -->
		<div class="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3 mb-8">
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
				<div class="text-xs text-gray-400 uppercase tracking-wide mb-1">인스턴스</div>
				<div class="text-2xl font-bold text-white">{data.totals.instances}</div>
			</div>
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
				<div class="text-xs text-gray-400 uppercase tracking-wide mb-1">CPU</div>
				<div class="text-2xl font-bold text-white">{data.totals.vcpus} <span class="text-base font-normal text-gray-400">cores</span></div>
			</div>
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
				<div class="text-xs text-gray-400 uppercase tracking-wide mb-1">RAM</div>
				<div class="text-2xl font-bold text-white">{formatRam(data.totals.ram_mb)}</div>
			</div>
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
				<div class="text-xs text-gray-400 uppercase tracking-wide mb-1">볼륨</div>
				<div class="text-2xl font-bold text-white">{data.totals.volumes}</div>
			</div>
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
				<div class="text-xs text-gray-400 uppercase tracking-wide mb-1">스토리지</div>
				<div class="text-2xl font-bold text-white">{data.totals.storage_gb} <span class="text-base font-normal text-gray-400">GB</span></div>
			</div>
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
				<div class="text-xs text-gray-400 uppercase tracking-wide mb-1">네트워크</div>
				<div class="text-2xl font-bold text-white">{data.totals.networks}</div>
			</div>
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
				<div class="text-xs text-gray-400 uppercase tracking-wide mb-1">Floating IP</div>
				<div class="text-2xl font-bold text-white">{data.totals.floating_ips}</div>
			</div>
		</div>

		<!-- 프로젝트별 섹션 -->
		<div class="space-y-3">
			{#each data.projects as proj (proj.project_id)}
				{@const isActive = proj.project_id === data.current_project_id}
				<div class="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
					<!-- 프로젝트 헤더 -->
					<button
						class="w-full flex items-center justify-between px-5 py-4 hover:bg-gray-800/50 transition-colors text-left"
						onclick={() => toggleProject(proj.project_id)}
					>
						<div class="flex items-center gap-3">
							<span class="text-sm font-medium text-white">{proj.project_name}</span>
							{#if isActive}
								<span class="px-1.5 py-0.5 rounded text-xs bg-blue-900/40 text-blue-400">현재</span>
							{/if}
							{#if proj.error}
								<span class="px-1.5 py-0.5 rounded text-xs bg-red-900/40 text-red-400">오류</span>
							{/if}
						</div>
						<div class="flex items-center gap-6 text-xs text-gray-400">
							<span>인스턴스 {proj.instance_count}</span>
							<span>볼륨 {proj.volume_count}</span>
							<span>{proj.storage_gb} GB</span>
							<svg class="w-4 h-4 transition-transform {expandedProject === proj.project_id ? 'rotate-180' : ''}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
							</svg>
						</div>
					</button>

					{#if expandedProject === proj.project_id}
						<div class="border-t border-gray-800 px-5 py-4 space-y-4">
							<!-- 인스턴스 목록 -->
							{#if proj.instances.length > 0}
								<div>
									<div class="text-xs text-gray-400 uppercase tracking-wide mb-2">인스턴스</div>
									<div class="space-y-1">
										{#each proj.instances as inst (inst.id)}
											<div class="flex items-center justify-between bg-gray-800/50 rounded-lg px-3 py-2 text-xs">
												<div class="flex items-center gap-3">
													<span class="text-gray-300 font-medium">{inst.name || inst.id.slice(0, 8)}</span>
													{#if inst.flavor_name}
														<span class="text-gray-500">{inst.flavor_name}</span>
													{/if}
												</div>
												<span class="{statusColor(inst.status)} font-medium">{inst.status}</span>
											</div>
										{/each}
									</div>
								</div>
							{/if}

							<!-- 볼륨 목록 -->
							{#if proj.volumes.length > 0}
								<div>
									<div class="text-xs text-gray-400 uppercase tracking-wide mb-2">볼륨</div>
									<div class="space-y-1">
										{#each proj.volumes as vol (vol.id)}
											<div class="flex items-center justify-between bg-gray-800/50 rounded-lg px-3 py-2 text-xs">
												<div class="flex items-center gap-3">
													<span class="text-gray-300 font-medium">{vol.name || vol.id.slice(0, 8)}</span>
													<span class="text-gray-500">{vol.size} GB</span>
												</div>
												<span class="{statusColor(vol.status)} font-medium">{vol.status}</span>
											</div>
										{/each}
									</div>
								</div>
							{/if}

							{#if proj.instances.length === 0 && proj.volumes.length === 0}
								<div class="text-center text-gray-600 text-xs py-4">리소스가 없습니다</div>
							{/if}
						</div>
					{/if}
				</div>
			{/each}
		</div>

		{#if data.projects.length === 0}
			<div class="text-center text-gray-500 text-sm py-12">소속 프로젝트가 없습니다</div>
		{/if}
	{/if}
</div>
