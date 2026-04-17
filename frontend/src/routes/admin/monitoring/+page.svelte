<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';

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
		};
		network: {
			network_count: number;
			router_count: number;
			router_active: number;
			floatingip_count: number;
			floatingip_active: number;
			port_count: number;
		};
		containers: {
			zun_count: number;
			k3s_count: number;
		};
	}

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	let summary = $state<MonitoringSummary | null>(null);
	let loading = $state(true);

	function pct(used: number, total: number) {
		if (!total) return 0;
		return Math.min(100, Math.round((used / total) * 100));
	}
	function barColor(p: number) {
		if (p >= 90) return 'bg-red-500';
		if (p >= 70) return 'bg-orange-500';
		if (p >= 50) return 'bg-yellow-500';
		return 'bg-blue-500';
	}
	function gb(mb: number) { return Math.round(mb / 1024); }

	async function load() {
		loading = true;
		try {
			summary = await api.get<MonitoringSummary>('/api/admin/monitoring/summary', token, projectId);
		} catch {
			summary = null;
		} finally {
			loading = false;
		}
	}

	onMount(load);
</script>

<div class="p-4 md:p-8 max-w-7xl">
	<div class="flex items-center justify-between mb-6">
		<h1 class="text-2xl font-bold text-white">통합 모니터링</h1>
		<button
			onclick={load}
			class="text-xs text-gray-400 hover:text-white transition-colors px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600"
		>
			새로고침
		</button>
	</div>

	{#if loading}
		<LoadingSkeleton variant="table" rows={6} />
	{:else if !summary}
		<div class="text-red-400 text-sm">모니터링 데이터를 불러올 수 없습니다.</div>
	{:else}
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
					<div class="flex justify-between text-xs text-gray-400 mb-1">
						<span>vCPU</span>
						<span>{summary.compute.vcpus_used} / {summary.compute.vcpus_total}</span>
					</div>
					<div class="w-full bg-gray-800 rounded-full h-2">
						<div
							class="{barColor(pct(summary.compute.vcpus_used, summary.compute.vcpus_total))} h-2 rounded-full transition-all"
							style="width: {pct(summary.compute.vcpus_used, summary.compute.vcpus_total)}%"
						></div>
					</div>
				</div>

				<!-- RAM -->
				<div class="mb-4">
					<div class="flex justify-between text-xs text-gray-400 mb-1">
						<span>RAM</span>
						<span>{gb(summary.compute.memory_used_mb)} GB / {gb(summary.compute.memory_total_mb)} GB</span>
					</div>
					<div class="w-full bg-gray-800 rounded-full h-2">
						<div
							class="{barColor(pct(summary.compute.memory_used_mb, summary.compute.memory_total_mb))} h-2 rounded-full transition-all"
							style="width: {pct(summary.compute.memory_used_mb, summary.compute.memory_total_mb)}%"
						></div>
					</div>
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

				<div class="mt-4 pt-4 border-t border-gray-800 flex items-center justify-between text-xs">
					<span class="text-gray-500">파일 스토리지</span>
					<span class="text-gray-300">{summary.storage.file_storage_count}개</span>
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
						<div class="text-xs text-gray-500 mt-1">k3s 클러스터</div>
					</div>
				</div>

				<div class="mt-4 pt-4 border-t border-gray-800 grid grid-cols-2 gap-2">
					<a href="/admin/containers" class="flex items-center justify-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 transition-colors bg-gray-800 rounded-lg py-2">
						컨테이너 목록 →
					</a>
					<a href="/admin/containers/k3s" class="flex items-center justify-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 transition-colors bg-gray-800 rounded-lg py-2">
						k3s 클러스터 →
					</a>
				</div>
			</div>
		</div>
	{/if}
</div>
