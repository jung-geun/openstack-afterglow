<script lang="ts">
	import type { ActiveTab } from '$lib/stores/k3sClusterDetailController.svelte';
	import { useK3sClusterDetailController } from '$lib/stores/k3sClusterDetailController.svelte';

	const s = useK3sClusterDetailController();

	const tabs: { key: ActiveTab; label: string }[] = [
		{ key: 'main',       label: '메인' },
		{ key: 'configmaps', label: 'ConfigMap' },
		{ key: 'secrets',    label: 'Secret' },
		{ key: 'services',   label: 'Service' },
		{ key: 'workloads',  label: 'Deployment / RS' },
		{ key: 'pods',       label: 'Pod' },
	];
</script>

<div class="flex flex-wrap gap-1 mb-5 border-b border-gray-800 pb-0">
	{#each tabs as tab}
		<button
			onclick={() => { s.activeTab = tab.key; }}
			class="px-3 py-2 text-xs font-medium rounded-t-lg transition-colors relative -mb-px border-b-2
				{s.activeTab === tab.key
					? 'border-blue-500 text-blue-400 bg-blue-900/10'
					: 'border-transparent text-gray-400 hover:text-gray-200 hover:bg-gray-800/50'}"
		>
			{tab.label}
		</button>
	{/each}
</div>
