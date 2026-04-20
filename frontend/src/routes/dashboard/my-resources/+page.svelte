<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { untrack } from 'svelte';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import RefreshButton from '$lib/components/RefreshButton.svelte';
	import AutoRefreshToggle from '$lib/components/AutoRefreshToggle.svelte';
	import StatusChip from '$lib/components/ui/StatusChip.svelte';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';

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

	// 전체 프로젝트 인스턴스/볼륨 플랫 목록
	const allInstances = $derived(
		data ? data.projects.flatMap(p => p.instances.map(inst => ({ ...inst, project: p.project_name }))) : []
	);
	const allVolumes = $derived(
		data ? data.projects.flatMap(p => p.volumes.map(vol => ({ ...vol, project: p.project_name }))) : []
	);

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
	<PageHeader breadcrumb="" title="내 리소스">
		{#snippet actions()}
			<AutoRefreshToggle bind:active={autoRefresh} intervalSeconds={30} />
			<RefreshButton {refreshing} onclick={forceRefresh} />
		{/snippet}
	</PageHeader>

	{#if error}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>
	{/if}

	{#if initialLoading}
		<div class="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
			{#each [1, 2, 3, 4] as _}
				<div class="animate-pulse bg-gray-900 border border-gray-800 rounded-2xl h-48"></div>
			{/each}
		</div>
	{:else if data}
		<div class="grid grid-cols-1 sm:grid-cols-2 gap-3.5">

			<!-- 인스턴스 카드 -->
			<div class="bg-gray-900 border border-gray-800 rounded-2xl p-5">
				<div class="flex items-center gap-2.5 mb-3.5">
					<div class="w-10 h-10 rounded-[10px] bg-blue-500/15 border border-blue-500/30 text-blue-400 flex items-center justify-center shrink-0">
						<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2" />
						</svg>
					</div>
					<div class="text-white font-semibold text-sm">인스턴스</div>
					<span class="ml-auto text-xs text-gray-500">{allInstances.length}개</span>
				</div>
				<div class="flex flex-col">
					{#each allInstances as inst, i (inst.id)}
						<div class="flex items-center gap-3 py-2.5 {i < allInstances.length - 1 ? 'border-b border-gray-800' : ''}">
							<div class="flex-1 min-w-0">
								<div class="text-white text-[13px] font-medium truncate">{inst.name || inst.id.slice(0, 8)}</div>
								<div class="text-[11px] text-gray-500 mt-0.5 font-mono truncate">{inst.flavor_name || '—'} · {inst.project}</div>
							</div>
							<StatusChip status={inst.status} />
						</div>
					{/each}
					{#if allInstances.length === 0}
						<div class="text-gray-600 text-xs py-3 text-center">없음</div>
					{/if}
				</div>
			</div>

			<!-- 블록 볼륨 카드 -->
			<div class="bg-gray-900 border border-gray-800 rounded-2xl p-5">
				<div class="flex items-center gap-2.5 mb-3.5">
					<div class="w-10 h-10 rounded-[10px] bg-cyan-500/15 border border-cyan-500/30 text-cyan-400 flex items-center justify-center shrink-0">
						<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
						</svg>
					</div>
					<div class="text-white font-semibold text-sm">블록 볼륨</div>
					<span class="ml-auto text-xs text-gray-500">{allVolumes.length}개</span>
				</div>
				<div class="flex flex-col">
					{#each allVolumes as vol, i (vol.id)}
						<div class="flex items-center gap-3 py-2.5 {i < allVolumes.length - 1 ? 'border-b border-gray-800' : ''}">
							<div class="flex-1 min-w-0">
								<div class="text-white text-[13px] font-medium truncate">{vol.name || vol.id.slice(0, 8)}</div>
								<div class="text-[11px] text-gray-500 mt-0.5 font-mono truncate">{vol.size} GB · {vol.volume_type || '—'}</div>
							</div>
							<StatusChip status={vol.status} />
						</div>
					{/each}
					{#if allVolumes.length === 0}
						<div class="text-gray-600 text-xs py-3 text-center">없음</div>
					{/if}
				</div>
			</div>

			<!-- 키페어 카드 -->
			<div class="bg-gray-900 border border-gray-800 rounded-2xl p-5">
				<div class="flex items-center gap-2.5 mb-3.5">
					<div class="w-10 h-10 rounded-[10px] bg-violet-500/15 border border-violet-500/30 text-violet-400 flex items-center justify-center shrink-0">
						<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
						</svg>
					</div>
					<div class="text-white font-semibold text-sm">키페어</div>
					<span class="ml-auto text-xs text-gray-500">{data.totals.instances > 0 ? '—' : '0'}개</span>
				</div>
				<div class="flex flex-col items-center justify-center py-6">
					<div class="text-[11px] text-gray-600 text-center leading-relaxed">
						키페어 목록은<br />
						<a href="/dashboard/compute/keypairs" class="text-violet-400 hover:text-violet-300 transition-colors">컴퓨트 → 키페어</a>에서 확인하세요
					</div>
				</div>
			</div>

			<!-- Floating IP 카드 -->
			<div class="bg-gray-900 border border-gray-800 rounded-2xl p-5">
				<div class="flex items-center gap-2.5 mb-3.5">
					<div class="w-10 h-10 rounded-[10px] bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 flex items-center justify-center shrink-0">
						<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
						</svg>
					</div>
					<div class="text-white font-semibold text-sm">Floating IP</div>
					<span class="ml-auto text-xs text-gray-500">{data.totals.floating_ips}개</span>
				</div>
				<div class="flex flex-col items-center justify-center py-6">
					<div class="text-[11px] text-gray-600 text-center leading-relaxed">
						Floating IP 목록은<br />
						<a href="/dashboard/network/floating-ips" class="text-emerald-400 hover:text-emerald-300 transition-colors">네트워크 → Floating IP</a>에서 확인하세요
					</div>
				</div>
			</div>

		</div>

		{#if data.projects.length === 0}
			<div class="text-center text-gray-500 text-sm py-12">소속 프로젝트가 없습니다</div>
		{/if}
	{/if}
</div>
