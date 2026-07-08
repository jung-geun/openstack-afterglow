<script lang="ts">
	import type { DashboardSummary } from '$lib/types/compute';
	import type { DashboardQuotas as Quotas } from '$lib/types/quotas';
	import StatTile from '$lib/components/ui/StatTile.svelte';

	let {
		summary,
		quotas,
		k3sCount,
		loading,
	}: {
		summary: DashboardSummary | null;
		quotas: Quotas | null;
		k3sCount: number | null;
		loading: boolean;
	} = $props();
</script>

{#if loading && !summary}
	<div class="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
		{#each Array(4) as _}
			<div class="bg-gray-900 border border-gray-800 rounded-2xl p-[18px] animate-pulse h-[82px]"></div>
		{/each}
	</div>
{:else}
	<div class="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
		<StatTile
			label="인스턴스"
			value={summary?.instances.total ?? 0}
			unit={quotas && quotas.compute.instances.limit > 0 ? `/ ${quotas.compute.instances.limit}` : undefined}
			accent="blue"
		>
			{#snippet icon()}
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2"/></svg>
			{/snippet}
		</StatTile>

		<StatTile
			label="블록 볼륨"
			value={quotas?.storage.volumes.in_use ?? 0}
			unit={quotas && quotas.storage.volumes.limit > 0 ? `/ ${quotas.storage.volumes.limit}` : (quotas?.storage.volumes.limit === -1 ? '/ 무제한' : undefined)}
			accent="cyan"
		>
			{#snippet icon()}
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4"/></svg>
			{/snippet}
		</StatTile>

		<StatTile
			label="Floating IP"
			value={quotas?.network.floatingip.in_use ?? 0}
			unit={quotas && quotas.network.floatingip.limit > 0 ? `/ ${quotas.network.floatingip.limit}` : (quotas?.network.floatingip.limit === -1 ? '/ 무제한' : undefined)}
			accent="violet"
		>
			{#snippet icon()}
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9"/></svg>
			{/snippet}
		</StatTile>

		<StatTile
			label="Drover 클러스터"
			value={k3sCount ?? '—'}
			unit={k3sCount !== null ? '활성' : undefined}
			accent="blue"
		>
			{#snippet icon()}
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linejoin="round" stroke-width="1.8" d="M12 2.4 19.8 6.1 21.7 14.3 16.3 20.8H7.7l-5.4-6.5 1.9-8.2L12 2.4Z"/><circle cx="12" cy="12" r="4.1" stroke-width="1.8"/><circle cx="12" cy="12" r="0.85" fill="currentColor" stroke="none"/><path stroke-linecap="round" stroke-width="1.8" d="M12 9.8V6.2M13.72 10.63l2.81-2.25M14.14 12.49l3.51.8M12.95 13.98l1.57 3.25M11.05 13.98l-1.57 3.25M9.86 12.49l-3.51.8M10.28 10.63 7.47 8.38"/></svg>
			{/snippet}
		</StatTile>
	</div>
{/if}
