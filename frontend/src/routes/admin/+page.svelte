<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { auth, isAdmin } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';

	// 관리자 전용 타입
	interface Overview {
		hypervisor_count: number;
		running_vms: number;
		gpu_instances: number;
		vcpus: { total: number; used: number };
		ram_gb: { total: number; used: number };
		disk_gb: { total: number; used: number };
		containers_count: number;
		shares_count: number;
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
	interface AdminContainer {
		uuid: string;
		name: string;
		status: string;
		image: string | null;
		cpu: number | null;
		memory: string | null;
		created_at: string | null;
	}
	interface AdminShare {
		id: string;
		name: string;
		status: string;
		size: number;
		share_proto: string;
		metadata: Record<string, string>;
	}
	interface PagedResponse<T> {
		items: T[];
		next_marker: string | null;
		count: number;
	}

	type Tab = 'overview' | 'hypervisors' | 'all-instances' | 'all-volumes' | 'all-containers' | 'all-shares';

	let activeTab = $state<Tab>('overview');
	let message = $state('');

	// Admin 전용 state
	let overview = $state<Overview | null>(null);
	let hypervisors = $state<Hypervisor[]>([]);
	let allInstances = $state<AdminInstance[]>([]);
	let allVolumes = $state<AdminVolume[]>([]);
	let allContainers = $state<AdminContainer[]>([]);
	let allShares = $state<AdminShare[]>([]);

	// 페이지네이션 상태
	let instancePageSize = $state(20);
	let instanceMarkerStack = $state<string[]>([]);
	let instanceNextMarker = $state<string | null>(null);
	let volumePageSize = $state(20);
	let volumeMarkerStack = $state<string[]>([]);
	let volumeNextMarker = $state<string | null>(null);

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
		Running:   'text-green-400',
		SHUTOFF:   'text-gray-400',
		Stopped:   'text-gray-400',
		ERROR:     'text-red-400',
		in_use:    'text-blue-400',
	};

	import { formatNumber, formatStorage } from '$lib/utils/format';

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

	async function loadAllInstances(marker?: string) {
		try {
			let url = `/api/admin/all-instances?limit=${instancePageSize}`;
			if (marker) url += `&marker=${marker}`;
			const res = await api.get<PagedResponse<AdminInstance>>(url, token, projectId);
			allInstances = res.items;
			instanceNextMarker = res.next_marker;
		} catch {
			allInstances = [];
		}
	}

	async function loadAllVolumes(marker?: string) {
		try {
			let url = `/api/admin/all-volumes?limit=${volumePageSize}`;
			if (marker) url += `&marker=${marker}`;
			const res = await api.get<PagedResponse<AdminVolume>>(url, token, projectId);
			allVolumes = res.items;
			volumeNextMarker = res.next_marker;
		} catch {
			allVolumes = [];
		}
	}

	async function loadAllContainers() {
		try {
			allContainers = await api.get<AdminContainer[]>('/api/admin/all-containers', token, projectId);
		} catch {
			allContainers = [];
		}
	}

	async function loadAllShares() {
		try {
			allShares = await api.get<AdminShare[]>('/api/admin/all-shares', token, projectId);
		} catch {
			allShares = [];
		}
	}

	async function switchTab(tab: Tab) {
		activeTab = tab;
		error = '';
		if (tab === 'overview' && !overview) await loadOverview();
		if (tab === 'hypervisors' && hypervisors.length === 0) await loadHypervisors();
		if (tab === 'all-instances' && allInstances.length === 0) {
			instanceMarkerStack = [];
			instanceNextMarker = null;
			await loadAllInstances();
		}
		if (tab === 'all-volumes' && allVolumes.length === 0) {
			volumeMarkerStack = [];
			volumeNextMarker = null;
			await loadAllVolumes();
		}
		if (tab === 'all-containers' && allContainers.length === 0) await loadAllContainers();
		if (tab === 'all-shares' && allShares.length === 0) await loadAllShares();
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
	<div class="flex gap-1 border-b border-gray-800 mb-6 flex-wrap">
		{#each [['overview', '개요'], ['hypervisors', '하이퍼바이저'], ['all-instances', '전체 인스턴스'], ['all-volumes', '전체 볼륨'], ['all-containers', '전체 컨테이너'], ['all-shares', '공유 스토리지']] as [tab, label]}
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
			<div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-4 mb-8">
				<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
					<div class="text-xs text-gray-500 mb-1">하이퍼바이저</div>
					<div class="text-2xl font-bold text-white">{formatNumber(overview.hypervisor_count)}</div>
				</div>
				<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
					<div class="text-xs text-gray-500 mb-1">총 VM</div>
					<div class="text-2xl font-bold text-white">{formatNumber(overview.running_vms)}</div>
				</div>
				<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
					<div class="text-xs text-gray-500 mb-1">GPU VM</div>
					<div class="text-2xl font-bold {overview.gpu_instances > 0 ? 'text-purple-300' : 'text-white'}">{formatNumber(overview.gpu_instances)}</div>
				</div>
				<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
					<div class="text-xs text-gray-500 mb-1">CPU 코어</div>
					<div class="text-2xl font-bold text-white">{formatNumber(overview.vcpus.used)}<span class="text-gray-600 text-base"> / {formatNumber(overview.vcpus.total)}</span></div>
					<div class="mt-2 bg-gray-800 rounded-full h-1.5"><div class="bg-blue-500 h-1.5 rounded-full" style="width:{usageBar(overview.vcpus.used, overview.vcpus.total)}%"></div></div>
				</div>
				<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
					<div class="text-xs text-gray-500 mb-1">RAM (GB)</div>
					<div class="text-2xl font-bold text-white">{formatNumber(overview.ram_gb.used)}<span class="text-gray-600 text-base"> / {formatNumber(overview.ram_gb.total)}</span></div>
					<div class="mt-2 bg-gray-800 rounded-full h-1.5"><div class="bg-purple-500 h-1.5 rounded-full" style="width:{usageBar(overview.ram_gb.used, overview.ram_gb.total)}%"></div></div>
				</div>
				<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
					<div class="text-xs text-gray-500 mb-1">로컬 디스크</div>
					<div class="text-xl font-bold text-white">{formatStorage(overview.disk_gb.used)}<span class="text-gray-600 text-sm"> / {formatStorage(overview.disk_gb.total)}</span></div>
					<div class="mt-2 bg-gray-800 rounded-full h-1.5"><div class="bg-orange-500 h-1.5 rounded-full" style="width:{usageBar(overview.disk_gb.used, overview.disk_gb.total)}%"></div></div>
				</div>
				<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
					<div class="text-xs text-gray-500 mb-1">컨테이너</div>
					<div class="text-2xl font-bold text-white">{formatNumber(overview.containers_count ?? 0)}</div>
				</div>
				<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
					<div class="text-xs text-gray-500 mb-1">공유 스토리지</div>
					<div class="text-2xl font-bold text-white">{formatNumber(overview.shares_count ?? 0)}</div>
				</div>
			</div>
			<div class="flex gap-3 flex-wrap">
				<button onclick={() => switchTab('hypervisors')} class="text-sm text-blue-400 hover:text-blue-300 transition-colors">하이퍼바이저 상세 →</button>
				<button onclick={() => switchTab('all-instances')} class="text-sm text-blue-400 hover:text-blue-300 transition-colors">전체 인스턴스 →</button>
				<button onclick={() => switchTab('all-containers')} class="text-sm text-blue-400 hover:text-blue-300 transition-colors">전체 컨테이너 →</button>
				<button onclick={() => switchTab('all-shares')} class="text-sm text-blue-400 hover:text-blue-300 transition-colors">공유 스토리지 →</button>
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
								<td class="py-2 pr-4 text-gray-400">{formatNumber(h.running_vms)}</td>
								<td class="py-2 pr-4 text-gray-400">{formatNumber(h.vcpus_used)}/{formatNumber(h.vcpus)}</td>
								<td class="py-2 pr-4 text-gray-400">{formatNumber(Math.round(h.memory_used_mb/1024))}/{formatNumber(Math.round(h.memory_size_mb/1024))}</td>
								<td class="py-2 text-gray-400">{formatStorage(h.local_disk_used_gb)}/{formatStorage(h.local_disk_gb)}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}

	{:else if activeTab === 'all-instances'}
		<div class="flex items-center gap-3 mb-4">
			<button onclick={() => { instanceMarkerStack = []; instanceNextMarker = null; loadAllInstances(); }} class="text-xs text-gray-400 hover:text-white transition-colors">새로고침</button>
			<div class="flex items-center gap-1 text-xs text-gray-500">
				표시:
				{#each [10, 20, 30] as n}
					<button
						onclick={() => { instancePageSize = n; instanceMarkerStack = []; instanceNextMarker = null; loadAllInstances(); }}
						class="px-2 py-0.5 rounded {instancePageSize === n ? 'bg-blue-600 text-white' : 'bg-gray-800 hover:bg-gray-700 text-gray-400'}"
					>{n}</button>
				{/each}
			</div>
		</div>
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
		<div class="flex items-center justify-between mt-3">
			<button
				disabled={instanceMarkerStack.length === 0}
				onclick={() => {
					const prev = instanceMarkerStack.slice(0, -1);
					const marker = prev[prev.length - 1];
					instanceMarkerStack = prev;
					loadAllInstances(marker);
				}}
				class="px-3 py-1.5 text-xs rounded bg-gray-800 hover:bg-gray-700 text-gray-300 disabled:opacity-30 disabled:cursor-not-allowed"
			>← 이전</button>
			<button
				disabled={!instanceNextMarker}
				onclick={() => {
					if (!instanceNextMarker) return;
					instanceMarkerStack = [...instanceMarkerStack, instanceNextMarker];
					loadAllInstances(instanceNextMarker);
				}}
				class="px-3 py-1.5 text-xs rounded bg-gray-800 hover:bg-gray-700 text-gray-300 disabled:opacity-30 disabled:cursor-not-allowed"
			>다음 →</button>
		</div>

	{:else if activeTab === 'all-volumes'}
		<div class="flex items-center gap-3 mb-4">
			<button onclick={() => { volumeMarkerStack = []; volumeNextMarker = null; loadAllVolumes(); }} class="text-xs text-gray-400 hover:text-white transition-colors">새로고침</button>
			<div class="flex items-center gap-1 text-xs text-gray-500">
				표시:
				{#each [10, 20, 30] as n}
					<button
						onclick={() => { volumePageSize = n; volumeMarkerStack = []; volumeNextMarker = null; loadAllVolumes(); }}
						class="px-2 py-0.5 rounded {volumePageSize === n ? 'bg-blue-600 text-white' : 'bg-gray-800 hover:bg-gray-700 text-gray-400'}"
					>{n}</button>
				{/each}
			</div>
		</div>
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
							<td class="py-2 pr-4 text-gray-400">{formatNumber(v.size)} GB</td>
							<td class="py-2 pr-4 text-gray-500 font-mono">{v.project_id?.slice(0, 8) ?? '-'}</td>
							<td class="py-2 text-gray-500">{v.created_at?.slice(0, 10) ?? '-'}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		<div class="flex items-center justify-between mt-3">
			<button
				disabled={volumeMarkerStack.length === 0}
				onclick={() => {
					const prev = volumeMarkerStack.slice(0, -1);
					const marker = prev[prev.length - 1];
					volumeMarkerStack = prev;
					loadAllVolumes(marker);
				}}
				class="px-3 py-1.5 text-xs rounded bg-gray-800 hover:bg-gray-700 text-gray-300 disabled:opacity-30 disabled:cursor-not-allowed"
			>← 이전</button>
			<button
				disabled={!volumeNextMarker}
				onclick={() => {
					if (!volumeNextMarker) return;
					volumeMarkerStack = [...volumeMarkerStack, volumeNextMarker];
					loadAllVolumes(volumeNextMarker);
				}}
				class="px-3 py-1.5 text-xs rounded bg-gray-800 hover:bg-gray-700 text-gray-300 disabled:opacity-30 disabled:cursor-not-allowed"
			>다음 →</button>
		</div>

	{:else if activeTab === 'all-containers'}
		<button onclick={loadAllContainers} class="text-xs text-gray-400 hover:text-white mb-4 transition-colors">새로고침</button>
		{#if allContainers.length === 0}
			<div class="text-gray-600 text-sm">컨테이너가 없습니다</div>
		{:else}
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
							<th class="text-left py-2 pr-4">이름</th>
							<th class="text-left py-2 pr-4">상태</th>
							<th class="text-left py-2 pr-4">이미지</th>
							<th class="text-left py-2 pr-4">CPU</th>
							<th class="text-left py-2 pr-4">메모리</th>
							<th class="text-left py-2">생성일</th>
						</tr>
					</thead>
					<tbody>
						{#each allContainers as c (c.uuid)}
							<tr class="border-b border-gray-800/50 text-xs">
								<td class="py-2 pr-4 text-white">{c.name || c.uuid.slice(0, 8)}</td>
								<td class="py-2 pr-4 {statusColor[c.status] ?? 'text-gray-400'}">{c.status}</td>
								<td class="py-2 pr-4 text-gray-400 font-mono text-xs">{c.image || '-'}</td>
								<td class="py-2 pr-4 text-gray-400">{c.cpu ?? '-'}</td>
								<td class="py-2 pr-4 text-gray-400">{c.memory || '-'}</td>
								<td class="py-2 text-gray-500">{c.created_at?.slice(0, 10) ?? '-'}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}

	{:else if activeTab === 'all-shares'}
		<button onclick={loadAllShares} class="text-xs text-gray-400 hover:text-white mb-4 transition-colors">새로고침</button>
		{#if allShares.length === 0}
			<div class="text-gray-600 text-sm">공유 스토리지가 없습니다</div>
		{:else}
			<div class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
							<th class="text-left py-2 pr-4">이름</th>
							<th class="text-left py-2 pr-4">상태</th>
							<th class="text-left py-2 pr-4">크기</th>
							<th class="text-left py-2 pr-4">프로토콜</th>
							<th class="text-left py-2">유형</th>
						</tr>
					</thead>
					<tbody>
						{#each allShares as s (s.id)}
							<tr class="border-b border-gray-800/50 text-xs">
								<td class="py-2 pr-4 text-white">{s.name || s.id.slice(0, 8)}</td>
								<td class="py-2 pr-4 {statusColor[s.status] ?? 'text-gray-400'}">{s.status}</td>
								<td class="py-2 pr-4 text-gray-400">{formatNumber(s.size)} GB</td>
								<td class="py-2 pr-4 text-gray-400">{s.share_proto}</td>
								<td class="py-2 text-gray-500">{s.metadata?.union_type || '-'}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}

	{/if}
</div>
