<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import { formatNumber, formatStorage } from '$lib/utils/format';

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

	let overview = $state<Overview | null>(null);
	let loading = $state(true);
	let error = $state('');

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	function usageBar(used: number, total: number): number {
		if (!total) return 0;
		return Math.min(100, Math.round(used / total * 100));
	}

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

<div class="p-8 max-w-6xl">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-white">관리자 개요</h1>
	</div>

	{#if error}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>
	{/if}

	{#if loading}
		<LoadingSkeleton variant="table" rows={5} />
	{:else if overview}
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
				<div class="mt-2 bg-gray-800 rounded-full h-1.5 overflow-hidden"><div class="bg-blue-500 h-1.5 rounded-full" style="width:{usageBar(overview.vcpus.used, overview.vcpus.total)}%"></div></div>
			</div>
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
				<div class="text-xs text-gray-500 mb-1">RAM (GB)</div>
				<div class="text-2xl font-bold text-white">{formatNumber(overview.ram_gb.used)}<span class="text-gray-600 text-base"> / {formatNumber(overview.ram_gb.total)}</span></div>
				<div class="mt-2 bg-gray-800 rounded-full h-1.5 overflow-hidden"><div class="bg-purple-500 h-1.5 rounded-full" style="width:{usageBar(overview.ram_gb.used, overview.ram_gb.total)}%"></div></div>
			</div>
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
				<div class="text-xs text-gray-500 mb-1">로컬 디스크</div>
				<div class="text-xl font-bold text-white">{formatStorage(overview.disk_gb.used)}<span class="text-gray-600 text-sm"> / {formatStorage(overview.disk_gb.total)}</span></div>
				<div class="mt-2 bg-gray-800 rounded-full h-1.5 overflow-hidden"><div class="bg-orange-500 h-1.5 rounded-full" style="width:{usageBar(overview.disk_gb.used, overview.disk_gb.total)}%"></div></div>
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
			<a href="/admin/hypervisors" class="text-sm text-blue-400 hover:text-blue-300 transition-colors">하이퍼바이저 상세 →</a>
			<a href="/admin/instances" class="text-sm text-blue-400 hover:text-blue-300 transition-colors">전체 인스턴스 →</a>
			<a href="/admin/containers" class="text-sm text-blue-400 hover:text-blue-300 transition-colors">전체 컨테이너 →</a>
			<a href="/admin/shares" class="text-sm text-blue-400 hover:text-blue-300 transition-colors">공유 스토리지 →</a>
			<a href="/admin/topology" class="text-sm text-blue-400 hover:text-blue-300 transition-colors">전체 토폴로지 →</a>
		</div>
	{:else}
		<div class="text-gray-500 text-sm">개요를 불러올 수 없습니다</div>
	{/if}
</div>
