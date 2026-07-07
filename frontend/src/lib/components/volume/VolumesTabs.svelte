<script lang="ts">
	let {
		tab = $bindable<'volumes' | 'snapshots'>(),
		volumeCount,
		snapshotCount,
		showSnapshots = true,
	}: {
		tab: 'volumes' | 'snapshots';
		volumeCount: number;
		snapshotCount: number;
		showSnapshots?: boolean;
	} = $props();
</script>

<div class="flex gap-1 mb-4 border-b border-gray-800">
	<button
		onclick={() => (tab = 'volumes')}
		class="px-4 py-2 text-[13px] font-medium border-b-2 -mb-px transition-colors {tab === 'volumes'
			? 'border-blue-500 text-white'
			: 'border-transparent text-gray-400 hover:text-gray-200'}"
	>
		볼륨 {volumeCount}
	</button>
	{#if showSnapshots}
		<button
			onclick={() => (tab = 'snapshots')}
			class="px-4 py-2 text-[13px] font-medium border-b-2 -mb-px transition-colors {tab === 'snapshots'
				? 'border-blue-500 text-white'
				: 'border-transparent text-gray-400 hover:text-gray-200'}"
		>
			스냅샷 {snapshotCount}
		</button>
	{/if}
</div>
