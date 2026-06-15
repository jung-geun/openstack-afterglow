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
			accent="emerald"
		>
			{#snippet icon()}
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 2l8 4v6c0 5.55 3.84 10.74 8 12 0 0-4.5 1.5-8 0C8.16 22.74 4 17.55 4 12V6l8-4z"/></svg>
			{/snippet}
		</StatTile>
	</div>
{/if}
