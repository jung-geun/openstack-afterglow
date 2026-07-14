<script lang="ts">
	import type { DashboardOverviewQuotas } from '$lib/types/quotas';
	import Card from '$lib/components/ui/Card.svelte';
	import Alert from '$lib/components/ui/Alert.svelte';
	import QuotaBar from '$lib/components/ui/QuotaBar.svelte';

	let {
		quotas,
		pending,
		error,
	}: {
		quotas: DashboardOverviewQuotas | null;
		pending: boolean;
		error: string | null;
	} = $props();
</script>

<Card padding="lg">
	<div class="text-[var(--color-ink-0)] text-[15px] font-semibold mb-3.5">쿼터 사용률</div>

	{#if error && quotas}
		<Alert tone="danger" class="mb-3">
			<span>쿼터를 불러오지 못했습니다</span>
		</Alert>
	{/if}

	{#if pending && !quotas}
		<div class="space-y-4">
			{#each Array(5) as _}
				<div class="h-8 bg-[var(--color-surface-sunken)] rounded animate-pulse"></div>
			{/each}
		</div>
	{:else if error && !quotas}
		<Alert tone="danger">
			<span>쿼터를 불러오지 못했습니다</span>
		</Alert>
	{:else if quotas}
		<div class="flex flex-col gap-3.5">
			<QuotaBar
				label="vCPU"
				used={quotas.compute.cores.in_use}
				limit={quotas.compute.cores.limit}
			/>
			<QuotaBar
				label="Memory (GB)"
				used={quotas.compute.ram.in_use / 1024}
				limit={quotas.compute.ram.limit === -1 ? -1 : quotas.compute.ram.limit / 1024}
			/>
			<QuotaBar
				label="Storage (GB)"
				used={quotas.storage.gigabytes.in_use}
				limit={quotas.storage.gigabytes.limit}
			/>
			<QuotaBar
				label="Floating IP"
				used={quotas.network.floatingip.in_use}
				limit={quotas.network.floatingip.limit}
			/>
			{#if quotas.file_storage}
				<QuotaBar
					label="Manila Shares"
					used={quotas.file_storage.shares.in_use}
					limit={quotas.file_storage.shares.limit}
				/>
			{/if}
		</div>
	{/if}
</Card>
