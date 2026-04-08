<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import QuotaDonut from '$lib/components/QuotaDonut.svelte';
	import { formatNumber, formatStorage } from '$lib/utils/format';

	interface Overview {
		hypervisor_count: number;
		running_vms: number;
		gpu_instances: number;
		vcpus: { total: number; allowed: number; used: number };
		ram_gb: { total: number; used: number };
		disk_gb: { total: number; used: number };
		containers_count: number;
		shares_count: number;
	}

	let overview = $state<Overview | null>(null);
	let loading = $state(true);
	let error = $state('');

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	onMount(async () => {
		try {
			overview = await api.get<Overview>('/api/admin/overview', token, projectId);
		} catch (e) {
			if (e instanceof ApiError && e.status === 403) { goto('/dashboard'); return; }
			error = e instanceof ApiError ? `조회 실패: ${e.message}` : '서버 오류';
		} finally {
			loading = false;
		}
	});
</script>

<div class="p-4 md:p-8 max-w-6xl">
	<div class="flex items-center justify-between mb-8">
		<h1 class="text-2xl font-bold text-white">관리자 개요</h1>
	</div>

	{#if error}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>
	{/if}

	{#if loading}
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
						label="로컬 디스크"
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
			<a href="/admin/shares" class="bg-gray-900 border border-gray-800 rounded-xl p-6 flex items-center gap-5 hover:border-gray-600 transition-colors">
				<div class="w-12 h-12 rounded-xl bg-yellow-600/20 flex items-center justify-center shrink-0">
					<svg class="w-6 h-6 text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"></path></svg>
				</div>
				<div>
					<div class="text-xs text-gray-500 uppercase tracking-wide mb-0.5">공유 스토리지</div>
					<div class="text-3xl font-bold text-white">{formatNumber(overview.shares_count ?? 0)}</div>
				</div>
			</a>
		</div>

		<!-- 퀵 링크 -->
		<div class="flex gap-3 flex-wrap">
			<a href="/admin/hypervisors" class="text-sm text-blue-400 hover:text-blue-300 transition-colors">하이퍼바이저 →</a>
			<a href="/admin/instances" class="text-sm text-blue-400 hover:text-blue-300 transition-colors">전체 인스턴스 →</a>
			<a href="/admin/containers" class="text-sm text-blue-400 hover:text-blue-300 transition-colors">전체 컨테이너 →</a>
			<a href="/admin/shares" class="text-sm text-blue-400 hover:text-blue-300 transition-colors">공유 스토리지 →</a>
			<a href="/admin/topology" class="text-sm text-blue-400 hover:text-blue-300 transition-colors">전체 토폴로지 →</a>
			<a href="/admin/networks" class="text-sm text-blue-400 hover:text-blue-300 transition-colors">네트워크 →</a>
		</div>
	{:else}
		<div class="text-gray-500 text-sm">개요를 불러올 수 없습니다</div>
	{/if}
</div>
