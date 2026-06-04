<script lang="ts">
	import type { DashboardSummary } from '$lib/types/compute';
	import type { DashboardQuotas as Quotas } from '$lib/types/quotas';
	import QuotaBar from '$lib/components/ui/QuotaBar.svelte';

	let {
		summary,
		quotas,
	}: {
		summary: DashboardSummary | null;
		quotas: Quotas | null;
	} = $props();
</script>

<div class="bg-gray-900 border border-gray-800 rounded-2xl p-5">
	<div class="text-white text-[15px] font-semibold mb-3.5">쿼터 사용률</div>
	{#if !quotas && !summary}
		<div class="space-y-4">
			{#each Array(5) as _}
				<div class="h-8 bg-gray-800 rounded animate-pulse"></div>
			{/each}
		</div>
	{:else}
		<div class="flex flex-col gap-3.5">
			{#if summary}
				<QuotaBar
					label="vCPU"
					used={summary.compute.vcpus_used}
					limit={summary.compute.vcpus_limit}
					color="bg-blue-500"
				/>
				<QuotaBar
					label="Memory (GB)"
					used={Math.round(summary.compute.ram_used_mb / 1024)}
					limit={Math.round(summary.compute.ram_limit_mb / 1024)}
					color="bg-cyan-400"
				/>
				<QuotaBar
					label="Storage (GB)"
					used={summary.storage.gigabytes_used}
					limit={summary.storage.gigabytes_limit}
					color="bg-violet-400"
				/>
			{/if}
			{#if quotas}
				<QuotaBar
					label="Floating IP"
					used={quotas.network.floatingip.in_use}
					limit={quotas.network.floatingip.limit}
					color="bg-amber-400"
				/>
				<QuotaBar
					label="Manila Shares"
					used={quotas.file_storage.shares.in_use}
					limit={quotas.file_storage.shares.limit}
					color="bg-teal-400"
				/>
			{/if}
		</div>
	{/if}
</div>
