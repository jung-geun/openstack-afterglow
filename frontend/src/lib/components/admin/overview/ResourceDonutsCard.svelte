<script lang="ts">
	import QuotaDonut from '$lib/components/QuotaDonut.svelte';
	import { formatNumber, formatStorage } from '$lib/utils/format';
	import type { Overview } from '$lib/types/adminOverview';

	let { overview }: { overview: Overview } = $props();
</script>

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
