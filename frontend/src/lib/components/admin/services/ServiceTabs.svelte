<script lang="ts">
	type TabKey = 'compute' | 'network' | 'block_storage' | 'shared_file_system' | 'orchestration' | 'container' | 'container_infra' | 'endpoints' | 'storage_pools';

	let {
		tabs,
		activeTab = $bindable(),
		loadingMap,
	}: {
		tabs: { key: TabKey; label: string; count: number }[];
		activeTab: TabKey;
		loadingMap: Record<TabKey, boolean>;
	} = $props();
</script>

<div class="flex flex-wrap gap-1 mb-6 border-b border-gray-800 pb-0">
	{#each tabs as tab}
		<button
			onclick={() => (activeTab = tab.key)}
			class="px-3 py-2 text-xs font-medium rounded-t-lg transition-colors relative -mb-px border-b-2 {activeTab === tab.key
				? 'border-blue-500 text-blue-400 bg-blue-900/10'
				: 'border-transparent text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'}"
		>
			{tab.label}
			{#if loadingMap[tab.key]}
				<span class="ml-1.5 inline-block w-3 h-3 border border-gray-500 border-t-blue-400 rounded-full animate-spin"></span>
			{:else}
				<span class="ml-1.5 text-xs px-1.5 py-0.5 rounded-full {activeTab === tab.key ? 'bg-blue-900/50 text-blue-300' : 'bg-gray-800 text-gray-500'}">{tab.count}</span>
			{/if}
		</button>
	{/each}
</div>
