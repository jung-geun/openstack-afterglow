<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { api } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import MetricsPanel from '$lib/components/instance/MetricsPanel.svelte';
	import QuotaBar from '$lib/components/ui/QuotaBar.svelte';
	import GrafanaEmbed from '$lib/components/monitoring/GrafanaEmbed.svelte';

	interface MonitoringSummary {
		compute: {
			hypervisors_total: number;
			hypervisors_up: number;
			vcpus_used: number;
			vcpus_total: number;
			memory_used_mb: number;
			memory_total_mb: number;
			running_vms: number;
			gpu_instances: number;
			instance_stats: { total: number; active: number; shutoff: number; error: number; other: number };
		};
		storage: {
			volume_count: number;
			volume_by_status: Record<string, number>;
			total_gb: number;
			file_storage_count: number;
			volume_snapshot_count?: number;
			volume_backup_count?: number;
			share_snapshot_count?: number;
			image_count?: number;
		};
		network: {
			network_count: number;
			router_count: number;
			router_active: number;
			floatingip_count: number;
			floatingip_active: number;
			port_count: number;
			subnet_count?: number;
			security_group_count?: number;
			load_balancer_count?: number;
			load_balancer_active?: number;
		};
		containers: {
			zun_count: number;
			k3s_count: number;
			k3s_active?: number;
		};
		data_services?: {
			database_instance_count: number;
		};
		identity?: {
			user_count: number;
			project_count: number;
		};
	}

	interface AdminInstance {
		id: string;
		name: string;
		status: string;
		project_id: string | null;
		flavor: string;
		host: string | null;
	}

	interface PagedResponse<T> {
		items: T[];
		next_marker: string | null;
		count: number;
	}

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	// --- 탭 ---
	let tab = $state<'summary' | 'instances' | 'infra'>('summary');

	// --- 클러스터 요약 ---
	let summary = $state<MonitoringSummary | null>(null);
	let loading = $state(true);
	let refreshing = $state(false);

	function pct(used: number, total: number) {
		if (!total) return 0;
		return Math.min(100, Math.round((used / total) * 100));
	}
	function gb(mb: number) { return Math.round(mb / 1024); }

	async function load() {
		if (!summary) loading = true;
		else refreshing = true;
		try {
			summary = await api.get<MonitoringSummary>('/api/admin/monitoring/summary', token, projectId);
		} catch {
			summary = null;
		} finally {
			loading = false;
			refreshing = false;
		}
	}

	const ar = createAutoRefresh(load, {
		storageKey: 'admin-monitoring',
		defaultActive: true,
		defaultInterval: 15,
		intervalOptions: [10, 15, 30, 60]
	});

	// --- 인스턴스 메트릭 ---
	let instanceList = $state<AdminInstance[]>([]);
	let loadingInstances = $state(false);
	let nextMarker = $state<string | null>(null);
	let search = $state('');
	let selectedInst = $state<AdminInstance | null>(null);

	const filtered = $derived(
		search
			? instanceList.filter(i =>
				i.name.toLowerCase().includes(search.toLowerCase()) ||
				(i.project_id ?? '').includes(search)
			)
			: instanceList
	);

	async function loadInstances(reset = false) {
		if (loadingInstances) return;
		if (reset) { instanceList = []; nextMarker = null; selectedInst = null; }
		loadingInstances = true;
		try {
			const marker = nextMarker && !reset ? `&marker=${nextMarker}` : '';
			const resp = await api.get<PagedResponse<AdminInstance>>(
				`/api/admin/all-instances?limit=50${marker}`,
				token,
				projectId,
			);
			instanceList = reset ? resp.items : [...instanceList, ...resp.items];
			nextMarker = resp.next_marker;
		} catch {
			// 목록 로드 실패는 UI에 빈 상태로 처리
		} finally {
			loadingInstances = false;
		}
	}

	$effect(() => {
		if (tab === 'instances' && instanceList.length === 0 && !loadingInstances) {
			loadInstances(true);
		}
	});
</script>

<div class="p-4 md:p-8 max-w-7xl mx-auto">
	<PageHeader breadcrumb="MONITORING" title="통합 모니터링">
		{#snippet actions()}
			{#if tab === 'summary'}
				<AutoRefreshControl
					bind:active={ar.active}
					bind:intervalSeconds={ar.intervalSeconds}
					intervalOptions={ar.intervalOptions}
					refreshing={loading || refreshing}
					onManualRefresh={load}
				/>
			{:else}
				<button
					onclick={() => loadInstances(true)}
					disabled={loadingInstances}
					class="text-xs px-3 py-1.5 rounded border border-gray-700 text-gray-400 hover:text-gray-200 hover:border-gray-500 disabled:opacity-40 transition-colors"
				>
					{loadingInstances ? '로딩 중...' : '새로고침'}
				</button>
			{/if}
		{/snippet}
	</PageHeader>

	<!-- 탭 -->
	<div class="flex gap-1 mb-6 border-b border-gray-800">
		<button
			onclick={() => (tab = 'summary')}
			class="px-4 py-2 text-sm font-medium transition-colors -mb-px border-b-2
				{tab === 'summary' ? 'text-white border-blue-500' : 'text-gray-500 border-transparent hover:text-gray-300'}"
		>클러스터 요약</button>
		<button
			onclick={() => (tab = 'instances')}
			class="px-4 py-2 text-sm font-medium transition-colors -mb-px border-b-2
				{tab === 'instances' ? 'text-white border-blue-500' : 'text-gray-500 border-transparent hover:text-gray-300'}"
		>인스턴스 메트릭</button>
		<button
			onclick={() => (tab = 'infra')}
			class="px-4 py-2 text-sm font-medium transition-colors -mb-px border-b-2
				{tab === 'infra' ? 'text-white border-blue-500' : 'text-gray-500 border-transparent hover:text-gray-300'}"
		>인프라 메트릭</button>
	</div>

	<!-- 클러스터 요약 탭 -->
	{#if tab === 'summary'}
		{#if loading}
			<LoadingSkeleton variant="table" rows={6} />
		{:else if !summary}
			<div class="text-red-400 text-sm">모니터링 데이터를 불러올 수 없습니다.</div>
		{:else}
			<div class:opacity-60={refreshing} class:pointer-events-none={refreshing}>
			<div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
				<!-- Compute -->
				<div class="bg-gray-900 border border-gray-800 rounded-xl p-5">
					<div class="flex items-center justify-between mb-4">
						<h2 class="text-sm font-semibold text-white">Compute</h2>
						<span class="text-xs text-gray-500">
							하이퍼바이저 <span class="text-green-400">{summary.compute.hypervisors_up}</span>/{summary.compute.hypervisors_total} up
						</span>
					</div>

					<!-- vCPU -->
					<div class="mb-4">
						<QuotaBar label="vCPU" used={summary.compute.vcpus_used} limit={summary.compute.vcpus_total} size="md" />
					</div>

					<!-- RAM -->
					<div class="mb-4">
						<QuotaBar label="RAM (GB)" used={gb(summary.compute.memory_used_mb)} limit={gb(summary.compute.memory_total_mb)} size="md" />
					</div>

					<!-- 인스턴스 상태 -->
					<div class="mt-4 grid grid-cols-4 gap-2 text-center">
						<div class="bg-gray-800 rounded-lg p-2">
							<div class="text-lg font-bold text-green-400">{summary.compute.instance_stats?.active ?? 0}</div>
							<div class="text-xs text-gray-500">ACTIVE</div>
						</div>
						<div class="bg-gray-800 rounded-lg p-2">
							<div class="text-lg font-bold text-gray-400">{summary.compute.instance_stats?.shutoff ?? 0}</div>
							<div class="text-xs text-gray-500">SHUTOFF</div>
						</div>
						<div class="bg-gray-800 rounded-lg p-2">
							<div class="text-lg font-bold text-red-400">{summary.compute.instance_stats?.error ?? 0}</div>
							<div class="text-xs text-gray-500">ERROR</div>
						</div>
						<div class="bg-gray-800 rounded-lg p-2">
							<div class="text-lg font-bold text-purple-400">{summary.compute.gpu_instances}</div>
							<div class="text-xs text-gray-500">GPU VM</div>
						</div>
					</div>

					<div class="mt-3 text-xs text-gray-500 text-right">
						총 {summary.compute.instance_stats?.total ?? 0}개 인스턴스
					</div>
				</div>

				<!-- Storage -->
				<div class="bg-gray-900 border border-gray-800 rounded-xl p-5">
					<h2 class="text-sm font-semibold text-white mb-4">스토리지</h2>

					<div class="grid grid-cols-2 gap-3 mb-4">
						<div class="bg-gray-800 rounded-lg p-3 text-center">
							<div class="text-2xl font-bold text-white">{summary.storage.volume_count}</div>
							<div class="text-xs text-gray-500 mt-1">볼륨</div>
						</div>
						<div class="bg-gray-800 rounded-lg p-3 text-center">
							<div class="text-2xl font-bold text-white">
								{summary.storage.total_gb >= 1024
									? (summary.storage.total_gb / 1024).toFixed(1) + ' TB'
									: summary.storage.total_gb + ' GB'}
							</div>
							<div class="text-xs text-gray-500 mt-1">총 용량</div>
						</div>
					</div>

					<!-- 볼륨 상태별 -->
					{#if Object.keys(summary.storage.volume_by_status).length > 0}
						<div class="space-y-1.5">
							{#each Object.entries(summary.storage.volume_by_status) as [status, count]}
								<div class="flex justify-between text-xs">
									<span class="{status === 'available' ? 'text-green-400' : status === 'in-use' ? 'text-blue-400' : status === 'error' ? 'text-red-400' : 'text-gray-400'}">{status}</span>
									<span class="text-gray-300">{count}개</span>
								</div>
							{/each}
						</div>
					{/if}

					<div class="mt-4 pt-4 border-t border-gray-800 space-y-1.5 text-xs">
						<div class="flex items-center justify-between">
							<span class="text-gray-500">파일 스토리지</span>
							<span class="text-gray-300">{summary.storage.file_storage_count}개</span>
						</div>
						<div class="flex items-center justify-between">
							<span class="text-gray-500">볼륨 스냅샷</span>
							<span class="text-gray-300">{summary.storage.volume_snapshot_count ?? 0}개</span>
						</div>
						<div class="flex items-center justify-between">
							<span class="text-gray-500">볼륨 백업</span>
							<span class="text-gray-300">{summary.storage.volume_backup_count ?? 0}개</span>
						</div>
						<div class="flex items-center justify-between">
							<span class="text-gray-500">파일 스냅샷</span>
							<span class="text-gray-300">{summary.storage.share_snapshot_count ?? 0}개</span>
						</div>
						<div class="flex items-center justify-between">
							<span class="text-gray-500">이미지</span>
							<span class="text-gray-300">{summary.storage.image_count ?? 0}개</span>
						</div>
					</div>
				</div>

				<!-- Network -->
				<div class="bg-gray-900 border border-gray-800 rounded-xl p-5">
					<h2 class="text-sm font-semibold text-white mb-4">네트워크</h2>

					<div class="grid grid-cols-2 gap-3 mb-3">
						<div class="bg-gray-800 rounded-lg p-3 text-center">
							<div class="text-2xl font-bold text-white">{summary.network.network_count}</div>
							<div class="text-xs text-gray-500 mt-1">네트워크</div>
						</div>
						<div class="bg-gray-800 rounded-lg p-3 text-center">
							<div class="text-2xl font-bold text-white">{summary.network.router_count}</div>
							<div class="text-xs text-gray-500 mt-1">
								라우터 <span class="text-green-400">({summary.network.router_active} active)</span>
							</div>
						</div>
						<div class="bg-gray-800 rounded-lg p-3 text-center">
							<div class="text-2xl font-bold text-white">{summary.network.floatingip_count}</div>
							<div class="text-xs text-gray-500 mt-1">
								Floating IP <span class="text-green-400">({summary.network.floatingip_active} active)</span>
							</div>
						</div>
						<div class="bg-gray-800 rounded-lg p-3 text-center">
							<div class="text-2xl font-bold text-white">{summary.network.port_count}</div>
							<div class="text-xs text-gray-500 mt-1">포트</div>
						</div>
					</div>

					<div class="mt-3 pt-4 border-t border-gray-800 space-y-1.5 text-xs">
						<div class="flex items-center justify-between">
							<span class="text-gray-500">서브넷</span>
							<span class="text-gray-300">{summary.network.subnet_count ?? 0}개</span>
						</div>
						<div class="flex items-center justify-between">
							<span class="text-gray-500">Security Group</span>
							<span class="text-gray-300">{summary.network.security_group_count ?? 0}개</span>
						</div>
						<div class="flex items-center justify-between">
							<span class="text-gray-500">Load Balancer</span>
							<span class="text-gray-300">
								{summary.network.load_balancer_count ?? 0}개
								{#if (summary.network.load_balancer_count ?? 0) > 0}
									<span class="text-green-400">({summary.network.load_balancer_active ?? 0} active)</span>
								{/if}
							</span>
						</div>
					</div>
				</div>

				<!-- Containers -->
				<div class="bg-gray-900 border border-gray-800 rounded-xl p-5">
					<h2 class="text-sm font-semibold text-white mb-4">컨테이너</h2>

					<div class="grid grid-cols-2 gap-3">
						<div class="bg-gray-800 rounded-lg p-4 text-center">
							<div class="text-2xl font-bold text-white">{summary.containers.zun_count}</div>
							<div class="text-xs text-gray-500 mt-1">Zun 컨테이너</div>
						</div>
						<div class="bg-gray-800 rounded-lg p-4 text-center">
							<div class="text-2xl font-bold text-white">{summary.containers.k3s_count}</div>
							<div class="text-xs text-gray-500 mt-1">
								Drover 클러스터
								{#if (summary.containers.k3s_count ?? 0) > 0}
									<span class="text-green-400">({summary.containers.k3s_active ?? 0} active)</span>
								{/if}
							</div>
						</div>
					</div>

					<div class="mt-4 pt-4 border-t border-gray-800 grid grid-cols-2 gap-2">
						<a href="/admin/containers" class="flex items-center justify-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 transition-colors bg-gray-800 rounded-lg py-2">
							컨테이너 목록 →
						</a>
						<a href="/admin/drover" class="flex items-center justify-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 transition-colors bg-gray-800 rounded-lg py-2">
							Drover 클러스터 →
						</a>
					</div>
				</div>

				<!-- 데이터 서비스 -->
				<div class="bg-gray-900 border border-gray-800 rounded-xl p-5">
					<h2 class="text-sm font-semibold text-white mb-4">데이터 서비스</h2>
					<div class="grid grid-cols-1 gap-3">
						<div class="bg-gray-800 rounded-lg p-4 text-center">
							<div class="text-2xl font-bold text-white">{summary.data_services?.database_instance_count ?? 0}</div>
							<div class="text-xs text-gray-500 mt-1">DB 인스턴스 (Trove)</div>
						</div>
					</div>
					<div class="mt-4 pt-4 border-t border-gray-800">
						<a href="/admin/database-instances" class="flex items-center justify-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 transition-colors bg-gray-800 rounded-lg py-2">
							DB 인스턴스 →
						</a>
					</div>
				</div>

				<!-- Identity -->
				<div class="bg-gray-900 border border-gray-800 rounded-xl p-5">
					<h2 class="text-sm font-semibold text-white mb-4">Identity</h2>
					<div class="grid grid-cols-2 gap-3">
						<div class="bg-gray-800 rounded-lg p-4 text-center">
							<div class="text-2xl font-bold text-white">{summary.identity?.user_count ?? 0}</div>
							<div class="text-xs text-gray-500 mt-1">사용자</div>
						</div>
						<div class="bg-gray-800 rounded-lg p-4 text-center">
							<div class="text-2xl font-bold text-white">{summary.identity?.project_count ?? 0}</div>
							<div class="text-xs text-gray-500 mt-1">프로젝트</div>
						</div>
					</div>
					<div class="mt-4 pt-4 border-t border-gray-800 grid grid-cols-2 gap-2">
						<a href="/admin/users" class="flex items-center justify-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 transition-colors bg-gray-800 rounded-lg py-2">
							사용자 →
						</a>
						<a href="/admin/projects" class="flex items-center justify-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 transition-colors bg-gray-800 rounded-lg py-2">
							프로젝트 →
						</a>
					</div>
				</div>
			</div>
			</div>
		{/if}
	{/if}

	<!-- 인프라 메트릭 탭 -->
	{#if tab === 'infra'}
		<div class="space-y-6">
			<div>
				<h3 class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">하이퍼바이저 (Node Exporter)</h3>
				<GrafanaEmbed dashboardKey="node" height={400} />
			</div>
			<div>
				<h3 class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">메시지큐 (RabbitMQ)</h3>
				<GrafanaEmbed dashboardKey="rabbitmq" height={400} />
			</div>
			<div>
				<h3 class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">데이터베이스 (MySQL)</h3>
				<GrafanaEmbed dashboardKey="mysqld" height={400} />
			</div>
			<div>
				<h3 class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">캐시 (Memcached)</h3>
				<GrafanaEmbed dashboardKey="memcached" height={400} />
			</div>
			<div>
				<h3 class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Coordination (etcd)</h3>
				<GrafanaEmbed dashboardKey="etcd" height={400} />
			</div>
		</div>
	{/if}

	<!-- 인스턴스 메트릭 탭 -->
	{#if tab === 'instances'}
		<div class="flex gap-4" style="min-height: calc(100vh - 200px)">
			<!-- 왼쪽: 인스턴스 목록 -->
			<div class="w-72 flex-shrink-0 bg-gray-900 border border-gray-800 rounded-xl overflow-hidden flex flex-col">
				<div class="p-3 border-b border-gray-800">
					<input
						type="text"
						placeholder="이름 또는 프로젝트 ID 검색"
						bind:value={search}
						class="w-full bg-gray-800 rounded-lg px-3 py-1.5 text-sm text-gray-300 placeholder-gray-600 outline-none focus:ring-1 focus:ring-blue-500"
					/>
				</div>

				<div class="overflow-y-auto flex-1">
					{#if loadingInstances && instanceList.length === 0}
						<div class="p-4 text-gray-600 text-sm text-center">인스턴스 목록 로딩 중...</div>
					{:else if filtered.length === 0}
						<div class="p-4 text-gray-600 text-sm text-center">
							{search ? '검색 결과 없음' : '인스턴스 없음'}
						</div>
					{:else}
						{#each filtered as inst (inst.id)}
							<button
								onclick={() => (selectedInst = inst)}
								class="w-full text-left px-3 py-2.5 border-b border-gray-800 hover:bg-gray-800 transition-colors
									{selectedInst?.id === inst.id ? 'bg-gray-800 border-l-2 border-l-blue-500 pl-2.5' : ''}"
							>
								<div class="flex items-center gap-2">
									<div class="w-1.5 h-1.5 rounded-full flex-shrink-0
										{inst.status === 'ACTIVE' ? 'bg-green-400' : inst.status === 'ERROR' ? 'bg-red-400' : 'bg-gray-500'}"></div>
									<span class="text-sm text-gray-200 truncate">{inst.name}</span>
									{#if inst.flavor.toLowerCase().startsWith('gpu.')}
										<span class="text-xs text-purple-400 bg-purple-900/30 px-1 rounded flex-shrink-0">GPU</span>
									{/if}
								</div>
								<div class="text-xs text-gray-500 pl-3.5 mt-0.5 truncate font-mono">
									{inst.project_id?.slice(0, 12) ?? '-'}
								</div>
							</button>
						{/each}
					{/if}

					{#if nextMarker && !search}
						<button
							onclick={() => loadInstances()}
							disabled={loadingInstances}
							class="w-full py-2.5 text-xs text-blue-400 hover:text-blue-300 disabled:text-gray-600 transition-colors"
						>
							{loadingInstances ? '로딩 중...' : '더 불러오기'}
						</button>
					{/if}
				</div>

				<div class="px-3 py-2 border-t border-gray-800 text-xs text-gray-600">
					{filtered.length}개 표시 / 총 {instanceList.length}개 로드
				</div>
			</div>

			<!-- 오른쪽: MetricsPanel -->
			<div class="flex-1 min-w-0">
				{#if selectedInst}
					<div class="bg-gray-900 border border-gray-800 rounded-xl p-5">
						<div class="flex items-center gap-3 mb-5">
							<span class="text-white font-semibold">{selectedInst.name}</span>
							<span class="text-xs text-gray-500 font-mono">{selectedInst.id.slice(0, 8)}…</span>
							<span class="text-xs px-2 py-0.5 rounded
								{selectedInst.status === 'ACTIVE' ? 'bg-green-900/30 text-green-400' :
								 selectedInst.status === 'ERROR' ? 'bg-red-900/30 text-red-400' :
								 'bg-gray-800 text-gray-400'}"
							>{selectedInst.status}</span>
							{#if selectedInst.flavor}
								<span class="text-xs text-gray-500">{selectedInst.flavor}</span>
							{/if}
						</div>
						<MetricsPanel
							instanceId={selectedInst.id}
							isGpu={selectedInst.flavor.toLowerCase().startsWith('gpu.')}
						/>
					</div>
				{:else}
					<div class="flex items-center justify-center h-64 bg-gray-900 border border-gray-800 rounded-xl">
						<div class="text-center">
							<div class="text-gray-600 text-sm mb-1">인스턴스를 선택하세요</div>
							<div class="text-gray-700 text-xs">왼쪽 목록에서 VM을 클릭하면 메트릭이 표시됩니다</div>
						</div>
					</div>
				{/if}
			</div>
		</div>
	{/if}
</div>
