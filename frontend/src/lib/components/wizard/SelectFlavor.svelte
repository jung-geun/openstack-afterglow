<script lang="ts">
	interface FlavorInfo {
		id: string;
		name: string;
		vcpus: number;
		ram: number;
		disk: number;
		extra_specs: Record<string, string>;
	}

	let { flavors, selectedId, onSelect }: {
		flavors: FlavorInfo[];
		selectedId: string | null;
		onSelect: (id: string, name: string) => void;
	} = $props();

	type FlavorCategory = 'all' | 'cpu' | 'gpu' | 'other';
	let activeCategory = $state<FlavorCategory>('all');

	function hasGpu(flavor: FlavorInfo): boolean {
		return Object.keys(flavor.extra_specs).some(
			(k) => k.toLowerCase().includes('gpu') || k.toLowerCase().includes('pci')
		);
	}

	function categorize(f: FlavorInfo): 'cpu' | 'gpu' | 'other' {
		if (f.name.startsWith('gpu.') || hasGpu(f)) return 'gpu';
		if (f.name.startsWith('cpu.')) return 'cpu';
		return 'other';
	}

	const counts = $derived({
		cpu: flavors.filter(f => categorize(f) === 'cpu').length,
		gpu: flavors.filter(f => categorize(f) === 'gpu').length,
		other: flavors.filter(f => categorize(f) === 'other').length,
	});

	const filteredFlavors = $derived(
		activeCategory === 'all'
			? flavors
			: flavors.filter(f => categorize(f) === activeCategory)
	);

	function ramLabel(mb: number): string {
		return mb >= 1024 ? `${mb / 1024} GB` : `${mb} MB`;
	}
</script>

<!-- 카테고리 필터 탭 -->
<div class="flex gap-2 mb-4">
	{#each ([
		{ key: 'all', label: `전체 (${flavors.length})` },
		{ key: 'cpu', label: `CPU (${counts.cpu})` },
		{ key: 'gpu', label: `GPU (${counts.gpu})` },
		{ key: 'other', label: `기타 (${counts.other})` },
	] as const) as tab}
		<button
			onclick={() => activeCategory = tab.key}
			class="px-3 py-1 rounded-lg text-xs font-medium transition-colors {activeCategory === tab.key
				? 'bg-blue-600 text-white'
				: 'bg-gray-800 text-gray-400 hover:bg-gray-700'}"
		>{tab.label}</button>
	{/each}
</div>

<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
	{#each filteredFlavors as flavor}
		<button
			onclick={() => onSelect(flavor.id, flavor.name)}
			class="text-left p-4 rounded-xl border transition-all {selectedId === flavor.id
				? 'border-blue-500 bg-blue-900/20'
				: 'border-gray-700 bg-gray-900 hover:border-gray-500'}"
		>
			<div class="flex items-start justify-between mb-2">
				<div class="font-medium text-white text-sm">{flavor.name}</div>
				{#if hasGpu(flavor)}
					<span class="px-1.5 py-0.5 bg-purple-900/40 text-purple-300 rounded text-xs">GPU</span>
				{/if}
			</div>
			<div class="text-xs text-gray-500 space-y-0.5">
				<div>vCPU: {flavor.vcpus}</div>
				<div>RAM: {ramLabel(flavor.ram)}</div>
				<div>디스크: {flavor.disk} GB</div>
			</div>
		</button>
	{/each}
</div>
