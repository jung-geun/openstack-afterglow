<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { auth, isAdmin } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';

	// 기존 Manila share 관리용
	interface Share {
		id: string;
		name: string;
		status: string;
		size: number;
		library_name: string | null;
		library_version: string | null;
		built_at: string | null;
		metadata: Record<string, string>;
	}
	interface LibraryConfig {
		id: string;
		name: string;
		version: string;
		available_prebuilt: boolean;
	}

	// 관리자 전용 타입
	interface Overview {
		hypervisor_count: number;
		vcpus: { total: number; used: number };
		ram_gb: { total: number; used: number };
		disk_gb: { total: number; used: number };
	}
	interface Hypervisor {
		id: string;
		name: string;
		state: string;
		status: string;
		vcpus: number;
		vcpus_used: number;
		memory_size_mb: number;
		memory_used_mb: number;
		local_disk_gb: number;
		local_disk_used_gb: number;
		running_vms: number;
	}
	interface AdminInstance {
		id: string;
		name: string;
		status: string;
		project_id: string | null;
		user_id: string | null;
		flavor: string;
		created_at: string | null;
	}
	interface AdminVolume {
		id: string;
		name: string;
		status: string;
		size: number;
		project_id: string | null;
		created_at: string | null;
	}

	type Tab = 'overview' | 'hypervisors' | 'all-instances' | 'all-volumes' | 'shares';

	let activeTab = $state<Tab>('overview');

	// Manila share 관리 state
	let shares = $state<Share[]>([]);
	let libraries = $state<LibraryConfig[]>([]);
	let building = $state<string | null>(null);
	let sharesLoading = $state(false);
	let message = $state('');

	// Admin 전용 state
	let overview = $state<Overview | null>(null);
	let hypervisors = $state<Hypervisor[]>([]);
	let allInstances = $state<AdminInstance[]>([]);
	let allVolumes = $state<AdminVolume[]>([]);

	let loading = $state(true);
	let error = $state('');

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	const statusColor: Record<string, string> = {
		available: 'text-green-400',
		creating:  'text-yellow-400',
		building:  'text-yellow-400',
		error:     'text-red-400',
		ACTIVE:    'text-green-400',
		SHUTOFF:   'text-gray-400',
		ERROR:     'text-red-400',
		in_use:    'text-blue-400',
	};

	async function loadShares() {
		sharesLoading = true;
		try {
			[shares, libraries] = await Promise.all([
				api.get<Share[]>('/api/admin/shares', token, projectId),
				api.get<LibraryConfig[]>('/api/libraries', token, projectId),
			]);
		} catch (e) {
			error = e instanceof ApiError ? `로드 실패: ${e.message}` : '서버 오류';
		} finally {
			sharesLoading = false;
		}
	}

	async function loadOverview() {
		try {
			overview = await api.get<Overview>('/api/admin/overview', token, projectId);
		} catch (e) {
			if (e instanceof ApiError && e.status === 403) goto('/dashboard');
			error = e instanceof ApiError ? `조회 실패: ${e.message}` : '서버 오류';
		}
	}

	async function loadHypervisors() {
		try {
			hypervisors = await api.get<Hypervisor[]>('/api/admin/hypervisors', token, projectId);
		} catch {
			hypervisors = [];
		}
	}

	async function loadAllInstances() {
		try {
			allInstances = await api.get<AdminInstance[]>('/api/admin/all-instances', token, projectId);
		} catch {
			allInstances = [];
		}
	}

	async function loadAllVolumes() {
		try {
			allVolumes = await api.get<AdminVolume[]>('/api/admin/all-volumes', token, projectId);
		} catch {
			allVolumes = [];
		}
	}

	async function buildShare(libId: string) {
		building = libId;
		message = '';
		error = '';
		try {
			const res = await api.post<{ share_id: string }>(
				`/api/admin/shares/build?library_id=${libId}`, {}, token, projectId
			);
			message = `Share 생성 시작됨 (ID: ${res.share_id})`;
			await loadShares();
		} catch (e) {
			error = e instanceof ApiError ? `빌드 실패: ${e.message}` : '서버 오류';
		} finally {
			building = null;
		}
	}

	async function switchTab(tab: Tab) {
		activeTab = tab;
		error = '';
		if (tab === 'shares' && shares.length === 0) await loadShares();
		if (tab === 'overview' && !overview) await loadOverview();
		if (tab === 'hypervisors' && hypervisors.length === 0) await loadHypervisors();
		if (tab === 'all-instances' && allInstances.length === 0) await loadAllInstances();
		if (tab === 'all-volumes' && allVolumes.length === 0) await loadAllVolumes();
	}

	onMount(async () => {
		if (!$isAdmin) { goto('/dashboard'); return; }
		await loadOverview();
		loading = false;
	});

	function usageBar(used: number, total: number): number {
		if (!total) return 0;
		return Math.min(100, Math.round(used / total * 100));
	}
</script>

<div class="p-8 max-w-6xl">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-white">관리자</h1>
	</div>

	{#if error}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>
	{/if}
	{#if message}
		<div class="bg-green-900/40 border border-green-700 text-green-300 rounded-lg px-4 py-3 text-sm mb-4">{message}</div>
	{/if}

	<!-- 탭 -->
	<div class="flex gap-1 border-b border-gray-800 mb-6">
		{#each [['overview', '개요'], ['hypervisors', '하이퍼바이저'], ['all-instances', '전체 인스턴스'], ['all-volumes', '전체 볼륨'], ['shares', '라이브러리 Share']] as [tab, label]}
			<button
				onclick={() => switchTab(tab as Tab)}
				class="px-4 py-2 text-sm transition-colors border-b-2 {activeTab === tab ? 'border-blue-500 text-white' : 'border-transparent text-gray-500 hover:text-gray-300'}"
			>{label}</button>
		{/each}
	</div>

	{#if loading}
		<LoadingSkeleton variant="table" rows={5} />
	{:else if activeTab === 'overview'}
		{#if overview}
			<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
				<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
					<div class="text-xs text-gray-500 mb-1">하이퍼바이저</div>
					<div class="text-2xl font-bold text-white">{overview.hypervisor_count}</div>
				</div>
				<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
					<div class="text-xs text-gray-500 mb-1">vCPU</div>
					<div class="text-2xl font-bold text-white">{overview.vcpus.used}<span class="text-gray-600 text-base"> / {overview.vcpus.total}</span></div>
					<div class="mt-2 bg-gray-800 rounded-full h-1.5"><div class="bg-blue-500 h-1.5 rounded-full" style="width:{usageBar(overview.vcpus.used, overview.vcpus.total)}%"></div></div>
				</div>
				<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
					<div class="text-xs text-gray-500 mb-1">RAM (GB)</div>
					<div class="text-2xl font-bold text-white">{overview.ram_gb.used}<span class="text-gray-600 text-base"> / {overview.ram_gb.total}</span></div>
					<div class="mt-2 bg-gray-800 rounded-full h-1.5"><div class="bg-purple-500 h-1.5 rounded-full" style="width:{usageBar(overview.ram_gb.used, overview.ram_gb.total)}%"></div></div>
				</div>
				<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
					<div class="text-xs text-gray-500 mb-1">로컬 디스크 (GB)</div>
					<div class="text-2xl font-bold text-white">{overview.disk_gb.used}<span class="text-gray-600 text-base"> / {overview.disk_gb.total}</span></div>
					<div class="mt-2 bg-gray-800 rounded-full h-1.5"><div class="bg-orange-500 h-1.5 rounded-full" style="width:{usageBar(overview.disk_gb.used, overview.disk_gb.total)}%"></div></div>
				</div>
			</div>
			<div class="flex gap-3">
				<button onclick={() => switchTab('hypervisors')} class="text-sm text-blue-400 hover:text-blue-300 transition-colors">하이퍼바이저 상세 →</button>
				<button onclick={() => switchTab('all-instances')} class="text-sm text-blue-400 hover:text-blue-300 transition-colors">전체 인스턴스 →</button>
			</div>
		{:else}
			<div class="text-gray-500 text-sm">개요를 불러올 수 없습니다</div>
		{/if}

	{:else if activeTab === 'hypervisors'}
		<button onclick={loadHypervisors} class="text-xs text-gray-400 hover:text-white mb-4 transition-colors">새로고침</button>
		{#if hypervisors.length === 0}
			<div class="text-gray-600 text-sm">하이퍼바이저가 없습니다</div>
		{:else}
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
							<th class="text-left py-2 pr-4">호스트명</th>
							<th class="text-left py-2 pr-4">상태</th>
							<th class="text-left py-2 pr-4">VM</th>
							<th class="text-left py-2 pr-4">vCPU</th>
							<th class="text-left py-2 pr-4">RAM (GB)</th>
							<th class="text-left py-2">로컬 디스크</th>
						</tr>
					</thead>
					<tbody>
						{#each hypervisors as h (h.id)}
							<tr class="border-b border-gray-800/50 text-xs">
								<td class="py-2 pr-4 text-white font-mono">{h.name}</td>
								<td class="py-2 pr-4">
									<span class="{h.state === 'up' && h.status === 'enabled' ? 'text-green-400' : 'text-red-400'}">{h.state}/{h.status}</span>
								</td>
								<td class="py-2 pr-4 text-gray-400">{h.running_vms}</td>
								<td class="py-2 pr-4 text-gray-400">{h.vcpus_used}/{h.vcpus}</td>
								<td class="py-2 pr-4 text-gray-400">{Math.round(h.memory_used_mb/1024)}/{Math.round(h.memory_size_mb/1024)}</td>
								<td class="py-2 text-gray-400">{h.local_disk_used_gb}/{h.local_disk_gb} GB</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}

	{:else if activeTab === 'all-instances'}
		<button onclick={loadAllInstances} class="text-xs text-gray-400 hover:text-white mb-4 transition-colors">새로고침</button>
		<div class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
						<th class="text-left py-2 pr-4">이름</th>
						<th class="text-left py-2 pr-4">상태</th>
						<th class="text-left py-2 pr-4">Flavor</th>
						<th class="text-left py-2 pr-4">프로젝트</th>
						<th class="text-left py-2">생성일</th>
					</tr>
				</thead>
				<tbody>
					{#each allInstances as s (s.id)}
						<tr class="border-b border-gray-800/50 text-xs">
							<td class="py-2 pr-4 text-white">{s.name || s.id.slice(0, 8)}</td>
							<td class="py-2 pr-4 {statusColor[s.status] ?? 'text-gray-400'}">{s.status}</td>
							<td class="py-2 pr-4 text-gray-400">{s.flavor || '-'}</td>
							<td class="py-2 pr-4 text-gray-500 font-mono">{s.project_id?.slice(0, 8) ?? '-'}</td>
							<td class="py-2 text-gray-500">{s.created_at?.slice(0, 10) ?? '-'}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>

	{:else if activeTab === 'all-volumes'}
		<button onclick={loadAllVolumes} class="text-xs text-gray-400 hover:text-white mb-4 transition-colors">새로고침</button>
		<div class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
						<th class="text-left py-2 pr-4">이름</th>
						<th class="text-left py-2 pr-4">상태</th>
						<th class="text-left py-2 pr-4">크기</th>
						<th class="text-left py-2 pr-4">프로젝트</th>
						<th class="text-left py-2">생성일</th>
					</tr>
				</thead>
				<tbody>
					{#each allVolumes as v (v.id)}
						<tr class="border-b border-gray-800/50 text-xs">
							<td class="py-2 pr-4 text-white">{v.name || v.id.slice(0, 8)}</td>
							<td class="py-2 pr-4 {statusColor[v.status] ?? 'text-gray-400'}">{v.status}</td>
							<td class="py-2 pr-4 text-gray-400">{v.size} GB</td>
							<td class="py-2 pr-4 text-gray-500 font-mono">{v.project_id?.slice(0, 8) ?? '-'}</td>
							<td class="py-2 text-gray-500">{v.created_at?.slice(0, 10) ?? '-'}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>

	{:else if activeTab === 'shares'}
		<!-- 기존 Manila share 관리 (원래 페이지 내용) -->
		<div class="mb-2">
			<h2 class="text-base font-semibold text-white mb-1">사전 빌드 상태</h2>
			<p class="text-xs text-gray-500 mb-4">Strategy A (사전 빌드)에서 사용할 Manila CephFS share를 관리합니다.</p>
		</div>

		{#if sharesLoading}
			<LoadingSkeleton variant="list" rows={4} />
		{:else}
			<div class="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-8">
				{#each libraries as lib}
					{@const prebuilt = shares.find(s => s.library_name === lib.id && s.metadata?.union_type === 'prebuilt')}
					<div class="bg-gray-900 border border-gray-700 rounded-xl p-4">
						<div class="flex items-start justify-between mb-2">
							<div>
								<div class="font-medium text-white text-sm">{lib.name}</div>
								<div class="text-xs text-gray-500">v{lib.version}</div>
							</div>
							{#if prebuilt}
								<span class="text-xs {statusColor[prebuilt.status] ?? 'text-gray-400'}">{prebuilt.status}</span>
							{:else}
								<span class="text-xs text-gray-600">미구축</span>
							{/if}
						</div>
						{#if prebuilt}
							<div class="text-xs text-gray-600 mb-3">
								Share ID: <span class="font-mono">{prebuilt.id.slice(0, 8)}...</span>
								{#if prebuilt.built_at}• {prebuilt.built_at.split('T')[0]}{/if}
							</div>
						{/if}
						<button
							onclick={() => buildShare(lib.id)}
							disabled={building === lib.id || !!prebuilt}
							class="w-full text-xs py-1.5 rounded-lg border transition-colors {prebuilt ? 'border-gray-700 text-gray-600 cursor-not-allowed' : 'border-blue-700 text-blue-400 hover:bg-blue-900/20'}"
						>
							{building === lib.id ? '생성 중...' : prebuilt ? '구축됨' : 'Share 생성'}
						</button>
					</div>
				{/each}
			</div>

			<div class="flex items-center justify-between mb-3">
				<h2 class="text-base font-semibold text-white">전체 Share 목록</h2>
				<button onclick={loadShares} class="text-gray-400 hover:text-white text-xs transition-colors">새로고침</button>
			</div>
			{#if shares.length === 0}
				<div class="text-gray-600 text-sm">Share가 없습니다</div>
			{:else}
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
							<th class="text-left py-2 pr-4">이름</th>
							<th class="text-left py-2 pr-4">상태</th>
							<th class="text-left py-2 pr-4">크기</th>
							<th class="text-left py-2 pr-4">타입</th>
							<th class="text-left py-2">라이브러리</th>
						</tr>
					</thead>
					<tbody>
						{#each shares as share}
							<tr class="border-b border-gray-800/50 text-xs">
								<td class="py-2 pr-4 font-mono text-gray-300">{share.name}</td>
								<td class="py-2 pr-4 {statusColor[share.status] ?? 'text-gray-400'}">{share.status}</td>
								<td class="py-2 pr-4 text-gray-400">{share.size} GB</td>
								<td class="py-2 pr-4 text-gray-500">{share.metadata?.union_type ?? '-'}</td>
								<td class="py-2 text-gray-500">{share.library_name ?? '-'}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			{/if}
		{/if}
	{/if}
</div>
