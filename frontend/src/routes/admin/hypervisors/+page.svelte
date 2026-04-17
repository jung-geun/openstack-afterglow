<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import { formatNumber, formatStorage } from '$lib/utils/format';
	import { projectNames } from '$lib/stores/projectNames';

	interface Hypervisor {
		id: string;
		name: string;
		state: string;
		status: string;
		vcpus: number;
		vcpus_used: number;
		vcpus_allowed: number;
		memory_size_mb: number;
		memory_used_mb: number;
		memory_allowed_mb: number;
		local_disk_gb: number;
		local_disk_used_gb: number;
		running_vms: number;
	}

	interface HypervisorDetail {
		id: string;
		hypervisor_hostname: string;
		state: string;
		status: string;
		hypervisor_type: string;
		hypervisor_version: number;
		host_ip: string;
		host_time: string;
		uptime: string;
		service_host: string;
		vcpus: number;
		vcpus_used: number;
		vcpus_allowed: number;
		memory_mb: number;
		memory_mb_used: number;
		memory_allowed_mb: number;
		local_gb: number;
		local_gb_used: number;
		running_vms: number;
		cpu_info: string | null;
		servers: { id: string; name: string; status: string; project_id: string; flavor: string }[];
	}

	let hypervisors = $state<Hypervisor[]>([]);
	let loading = $state(true);
	let sortColumn = $state('');
	let sortAsc = $state(true);

	let selectedDetail = $state<HypervisorDetail | null>(null);
	let detailLoading = $state(false);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function load() {
		loading = true;
		try {
			hypervisors = await api.get<Hypervisor[]>('/api/admin/hypervisors', token, projectId);
		} catch {
			hypervisors = [];
		} finally {
			loading = false;
		}
	}

	async function loadDetail(hvId: string) {
		detailLoading = true;
		selectedDetail = null;
		try {
			selectedDetail = await api.get<HypervisorDetail>(`/api/admin/hypervisors/${hvId}`, token, projectId);
		} catch {
			selectedDetail = null;
		} finally {
			detailLoading = false;
		}
	}

	function toggleSort(col: string) {
		if (sortColumn === col) {
			sortAsc = !sortAsc;
		} else {
			sortColumn = col;
			sortAsc = true;
		}
	}

	function sortIcon(col: string): string {
		if (sortColumn !== col) return '↕';
		return sortAsc ? '↑' : '↓';
	}

	function usageColor(used: number, total: number): string {
		if (total === 0) return 'bg-gray-600';
		const pct = used / total;
		if (pct >= 0.9) return 'bg-red-500';
		if (pct >= 0.7) return 'bg-orange-500';
		if (pct >= 0.5) return 'bg-yellow-500';
		return 'bg-blue-500';
	}

	function usagePct(used: number, total: number): number {
		if (total === 0) return 0;
		return Math.min(100, Math.round((used / total) * 100));
	}

	let sortedHypervisors = $derived(
		hypervisors.toSorted((a, b) => {
			if (!sortColumn) return 0;
			let va: string | number;
			let vb: string | number;
			if (sortColumn === 'name') {
				va = a.name;
				vb = b.name;
			} else {
				va = (a as Record<string, number>)[sortColumn] ?? 0;
				vb = (b as Record<string, number>)[sortColumn] ?? 0;
			}
			const cmp = typeof va === 'string' ? va.localeCompare(vb as string) : (va as number) - (vb as number);
			return sortAsc ? cmp : -cmp;
		})
	);

	// 마이그레이션
	let showMigrateModal = $state(false);
	let migrateServerId = $state('');
	let migrateServerName = $state('');
	let migrateType = $state<'live' | 'cold'>('live');
	let migrateHosts = $state<{ name: string }[]>([]);
	let migrateHost = $state('');
	let migrateLoading = $state(false);
	let migrateError = $state('');

	async function openMigrateModal(serverId: string, serverName: string, type: 'live' | 'cold') {
		migrateServerId = serverId;
		migrateServerName = serverName;
		migrateType = type;
		migrateHost = '';
		migrateError = '';
		migrateHosts = [];
		showMigrateModal = true;
		try {
			migrateHosts = await api.get<{ name: string }[]>('/api/admin/compute-hosts', token, projectId);
		} catch {
			migrateHosts = [];
		}
	}

	async function doMigrate() {
		migrateLoading = true;
		migrateError = '';
		try {
			if (migrateType === 'live') {
				await api.post(
					`/api/admin/instances/${migrateServerId}/live-migrate`,
					{ host: migrateHost || null, block_migration: 'auto' },
					token, projectId
				);
			} else {
				await api.post(
					`/api/admin/instances/${migrateServerId}/cold-migrate`,
					{},
					token, projectId
				);
			}
			showMigrateModal = false;
			// 현재 열린 하이퍼바이저 상세 새로고침
			if (selectedDetail) await loadDetail(selectedDetail.id);
		} catch (e) {
			migrateError = e instanceof ApiError ? e.message : '마이그레이션 실패';
		} finally {
			migrateLoading = false;
		}
	}

	onMount(() => {
		load();
		projectNames.load(token, projectId);
	});
</script>

<div class="flex h-full">
<div class="flex-1 p-4 md:p-8 max-w-6xl overflow-auto">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-white">하이퍼바이저</h1>
		<button onclick={load} class="text-xs text-gray-400 hover:text-white transition-colors px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600">새로고침</button>
	</div>

	{#if loading}
		<LoadingSkeleton variant="table" rows={5} />
	{:else if hypervisors.length === 0}
		<div class="text-gray-600 text-sm">하이퍼바이저가 없습니다</div>
	{:else}
		<div class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
						<th class="text-left py-2 pr-4">
							<button onclick={() => toggleSort('name')} class="hover:text-white transition-colors flex items-center gap-1">
								호스트명 <span class="text-gray-600">{sortIcon('name')}</span>
							</button>
						</th>
						<th class="text-left py-2 pr-4">상태</th>
						<th class="text-left py-2 pr-4">
							<button onclick={() => toggleSort('running_vms')} class="hover:text-white transition-colors flex items-center gap-1">
								VM <span class="text-gray-600">{sortIcon('running_vms')}</span>
							</button>
						</th>
						<th class="text-left py-2 pr-4">
							<button onclick={() => toggleSort('vcpus_used')} class="hover:text-white transition-colors flex items-center gap-1">
								vCPU <span class="text-gray-600">{sortIcon('vcpus_used')}</span>
							</button>
						</th>
						<th class="text-left py-2 pr-4">
							<button onclick={() => toggleSort('memory_used_mb')} class="hover:text-white transition-colors flex items-center gap-1">
								RAM (GB) <span class="text-gray-600">{sortIcon('memory_used_mb')}</span>
							</button>
						</th>
						<th class="text-left py-2">로컬 디스크</th>
					</tr>
				</thead>
				<tbody>
					{#each sortedHypervisors as h (h.id)}
						<tr
							class="border-b border-gray-800/50 text-xs cursor-pointer hover:bg-gray-800/50 transition-colors {selectedDetail?.id === h.id ? 'bg-gray-800/70' : ''}"
							onclick={() => loadDetail(h.id)}
						>
							<td class="py-2 pr-4 text-white font-mono">{h.name}</td>
							<td class="py-2 pr-4">
								<span class="{h.state === 'up' && h.status === 'enabled' ? 'text-green-400' : 'text-red-400'}">{h.state}/{h.status}</span>
							</td>
							<td class="py-2 pr-4 text-gray-400">{formatNumber(h.running_vms)}</td>
							<td class="py-2 pr-4">
								<div class="flex items-center gap-2">
									<div class="w-14 bg-gray-800 rounded-full h-1.5 flex-shrink-0">
										<div class="{usageColor(h.vcpus_used, h.vcpus_allowed || h.vcpus)} h-1.5 rounded-full" style="width: {usagePct(h.vcpus_used, h.vcpus_allowed || h.vcpus)}%"></div>
									</div>
									<span class="text-gray-400 text-xs">{formatNumber(h.vcpus_used)}/{formatNumber(h.vcpus_allowed || h.vcpus)}</span>
								</div>
							</td>
							<td class="py-2 pr-4">
								<div class="flex items-center gap-2">
									<div class="w-14 bg-gray-800 rounded-full h-1.5 flex-shrink-0">
										<div class="{usageColor(h.memory_used_mb, h.memory_allowed_mb || h.memory_size_mb)} h-1.5 rounded-full" style="width: {usagePct(h.memory_used_mb, h.memory_allowed_mb || h.memory_size_mb)}%"></div>
									</div>
									<span class="text-gray-400 text-xs">{formatNumber(Math.round(h.memory_used_mb/1024))}/{formatNumber(Math.round((h.memory_allowed_mb || h.memory_size_mb)/1024))}</span>
								</div>
							</td>
							<td class="py-2">
								<div class="flex items-center gap-2">
									<div class="w-14 bg-gray-800 rounded-full h-1.5 flex-shrink-0">
										<div class="{usageColor(h.local_disk_used_gb, h.local_disk_gb)} h-1.5 rounded-full" style="width: {usagePct(h.local_disk_used_gb, h.local_disk_gb)}%"></div>
									</div>
									<span class="text-gray-400 text-xs">{formatStorage(h.local_disk_used_gb)}/{formatStorage(h.local_disk_gb)}</span>
								</div>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>

<!-- 상세 슬라이드 패널 -->
{#if selectedDetail !== null || detailLoading}
	<div class="w-96 border-l border-gray-800 bg-gray-950 flex flex-col overflow-hidden flex-shrink-0">
		<div class="flex items-center justify-between px-4 py-3 border-b border-gray-800">
			<h2 class="text-sm font-semibold text-white truncate">{selectedDetail?.hypervisor_hostname ?? '로딩 중...'}</h2>
			<button onclick={() => { selectedDetail = null; }} class="text-gray-400 hover:text-white text-lg leading-none">×</button>
		</div>

		{#if detailLoading}
			<div class="p-4"><LoadingSkeleton variant="table" rows={4} /></div>
		{:else if selectedDetail}
			<div class="flex-1 overflow-y-auto p-4 space-y-4">
				<!-- 기본 정보 -->
				<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
					<h3 class="text-xs text-gray-500 uppercase tracking-wide mb-3">기본 정보</h3>
					<dl class="space-y-2 text-xs">
						<div class="flex justify-between">
							<dt class="text-gray-400">상태</dt>
							<dd class="{selectedDetail.state === 'up' && selectedDetail.status === 'enabled' ? 'text-green-400' : 'text-red-400'}">{selectedDetail.state}/{selectedDetail.status}</dd>
						</div>
						<div class="flex justify-between">
							<dt class="text-gray-400">호스트 IP</dt>
							<dd class="text-gray-300 font-mono">{selectedDetail.host_ip || '-'}</dd>
						</div>
						{#if selectedDetail.host_time}
						<div class="flex justify-between">
							<dt class="text-gray-400">호스트 시간</dt>
							<dd class="text-gray-300 font-mono">{selectedDetail.host_time}</dd>
						</div>
						{/if}
						{#if selectedDetail.uptime}
						<div class="flex justify-between gap-4">
							<dt class="text-gray-400 flex-shrink-0">업타임</dt>
							<dd class="text-gray-300 text-right text-xs leading-relaxed break-all">{selectedDetail.uptime}</dd>
						</div>
						{/if}
						<div class="flex justify-between">
							<dt class="text-gray-400">타입</dt>
							<dd class="text-gray-300">{selectedDetail.hypervisor_type}</dd>
						</div>
						<div class="flex justify-between">
							<dt class="text-gray-400">버전</dt>
							<dd class="text-gray-300">{selectedDetail.hypervisor_version}</dd>
						</div>
						<div class="flex justify-between">
							<dt class="text-gray-400">서비스 호스트</dt>
							<dd class="text-gray-300 font-mono">{selectedDetail.service_host || '-'}</dd>
						</div>
					</dl>
				</div>

				<!-- 리소스 현황 -->
				<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
					<h3 class="text-xs text-gray-500 uppercase tracking-wide mb-3">리소스 현황</h3>
					<dl class="space-y-2 text-xs">
						<div class="flex justify-between">
							<dt class="text-gray-400">vCPU</dt>
							<dd class="text-gray-300">{selectedDetail.vcpus_used} / {selectedDetail.vcpus_allowed || selectedDetail.vcpus} <span class="text-gray-600 text-xs">(물리 {selectedDetail.vcpus})</span></dd>
						</div>
						<div class="flex justify-between">
							<dt class="text-gray-400">RAM</dt>
							<dd class="text-gray-300">{formatNumber(Math.round(selectedDetail.memory_mb_used/1024))} / {formatNumber(Math.round((selectedDetail.memory_allowed_mb || selectedDetail.memory_mb)/1024))} GB <span class="text-gray-600 text-xs">(물리 {formatNumber(Math.round(selectedDetail.memory_mb/1024))} GB)</span></dd>
						</div>
						<div class="flex justify-between">
							<dt class="text-gray-400">로컬 디스크</dt>
							<dd class="text-gray-300">{formatStorage(selectedDetail.local_gb_used)} / {formatStorage(selectedDetail.local_gb)}</dd>
						</div>
						<div class="flex justify-between">
							<dt class="text-gray-400">실행 중 VM</dt>
							<dd class="text-gray-300">{selectedDetail.running_vms}</dd>
						</div>
					</dl>
				</div>

				<!-- VM 목록 -->
				{#if selectedDetail.servers.length > 0}
					<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
						<h3 class="text-xs text-gray-500 uppercase tracking-wide mb-3">VM 목록 ({selectedDetail.servers.length})</h3>
						<div class="space-y-1.5">
							{#each selectedDetail.servers as s}
								<div class="flex items-center justify-between py-1.5 border-b border-gray-800/50 last:border-0">
									<div class="flex-1 min-w-0">
										<div class="text-xs text-gray-300 truncate">{s.name || s.id.slice(0, 12)}</div>
										<div class="text-xs text-gray-500">{$projectNames[s.project_id] || s.project_id.slice(0, 8)} · {s.flavor}</div>
									</div>
									<div class="flex items-center gap-1 ml-2 flex-shrink-0">
										<span class="text-xs {s.status === 'ACTIVE' ? 'text-green-400' : s.status === 'ERROR' ? 'text-red-400' : 'text-gray-400'}">{s.status}</span>
										{#if s.status === 'ACTIVE'}
											<button onclick={() => openMigrateModal(s.id, s.name, 'live')} class="px-1.5 py-0.5 text-xs bg-cyan-900/30 hover:bg-cyan-900/60 text-cyan-400 rounded">이동</button>
										{:else if s.status === 'SHUTOFF'}
											<button onclick={() => openMigrateModal(s.id, s.name, 'cold')} class="px-1.5 py-0.5 text-xs bg-teal-900/30 hover:bg-teal-900/60 text-teal-400 rounded">이동</button>
										{/if}
									</div>
								</div>
							{/each}
						</div>
					</div>
				{/if}
			</div>
		{/if}
	</div>
{/if}
</div>

<!-- 마이그레이션 모달 -->
{#if showMigrateModal}
	<div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" role="dialog" onclick={() => { showMigrateModal = false; }} onkeydown={(e) => e.key === 'Escape' && (showMigrateModal = false)} tabindex="-1">
		<div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()}>
			<h2 class="text-lg font-semibold text-white mb-1">{migrateType === 'live' ? '라이브 마이그레이션' : '콜드 마이그레이션'}</h2>
			<p class="text-xs text-gray-500 mb-1"><span class="text-gray-300">{migrateServerName}</span></p>
			<p class="text-xs text-gray-500 mb-5">{migrateType === 'live' ? '인스턴스 실행 중에 다른 호스트로 이동합니다.' : '인스턴스를 종료하고 다른 호스트로 이동합니다.'}</p>
			{#if migrateError}
				<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{migrateError}</div>
			{/if}
			<div>
				<label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">대상 호스트 <span class="text-gray-600">(선택 안 하면 자동)</span></label>
				<select bind:value={migrateHost} class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500">
					<option value="">자동 선택</option>
					{#each migrateHosts as h}
						<option value={h.name}>{h.name}</option>
					{/each}
				</select>
			</div>
			<div class="flex justify-end gap-3 mt-6">
				<button onclick={() => { showMigrateModal = false; }} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">취소</button>
				<button onclick={doMigrate} disabled={migrateLoading} class="px-4 py-2 bg-cyan-700 hover:bg-cyan-600 text-white text-sm font-medium rounded-lg disabled:opacity-30">
					{migrateLoading ? '마이그레이션 중...' : '마이그레이션'}
				</button>
			</div>
		</div>
	</div>
{/if}
