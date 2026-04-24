<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api/client';
	import { auth } from '$lib/stores/auth';

	interface FlavorInfo {
		id: string;
		name: string;
		vcpus: number;
		ram: number;
		disk: number;
		extra_specs: Record<string, string>;
	}

	interface GpuTypeAvailability {
		device_name: string;
		vendor: string;
		total: number;
		used: number;
		available: number;
	}

	let { flavors, selectedId, onSelect }: {
		flavors: FlavorInfo[];
		selectedId: string | null;
		onSelect: (id: string, name: string) => void;
	} = $props();

	let gpuAvailability = $state<GpuTypeAvailability[]>([]);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	onMount(async () => {
		try {
			const data = await api.get<{ gpu_types: GpuTypeAvailability[] }>(
				'/api/dashboard/gpu-available', token, projectId
			);
			gpuAvailability = data.gpu_types ?? [];
		} catch (e) {
			// gpu_available_visible=false 또는 비활성화 — 조용히 무시
			if (e instanceof Error && !e.message.includes('404')) {
				console.warn('[SelectFlavor] GPU 가용량 조회 실패:', e.message);
			}
		}
	});

	function parseGpuRequest(f: FlavorInfo): { model: string; count: number }[] {
		const alias = f.extra_specs?.['pci_passthrough:alias'] ?? '';
		if (!alias) return [];
		return alias.split(',')
			.map(e => e.trim())
			.filter(e => e.includes(':') && !e.toLowerCase().includes('audio'))
			.map(e => {
				const idx = e.lastIndexOf(':');
				return { model: e.slice(0, idx).trim(), count: parseInt(e.slice(idx + 1)) || 1 };
			});
	}

	const selectedGpuRequest = $derived((() => {
		const map = new Map<string, number>();
		if (!selectedId || !gpuAvailability.length) return map;
		const f = flavors.find(fl => fl.id === selectedId);
		if (!f) return map;
		for (const r of parseGpuRequest(f)) {
			const matched = gpuAvailability.find(g =>
				g.device_name.replace(/\s+/g, '').toUpperCase().includes(r.model.toUpperCase()) ||
				r.model.toUpperCase().includes(g.device_name.replace(/\s+/g, '').toUpperCase())
			);
			if (matched) {
				map.set(matched.device_name, (map.get(matched.device_name) ?? 0) + r.count);
			}
		}
		return map;
	})());

	type FlavorCategory = 'all' | 'cpu' | 'gpu' | 'other';
	let activeCategory = $state<FlavorCategory>('all');
	let filterVcpus = $state<number | null>(null);
	let filterRam = $state<number | null>(null);
	let filterGpu = $state<string | null>(null);

	function extractGpuModel(f: FlavorInfo): string {
		const match = f.name.match(/^gpu\.([^_]+)/);
		return match ? match[1].toUpperCase() : 'Unknown';
	}

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

	const categoryFiltered = $derived(
		activeCategory === 'all'
			? flavors
			: flavors.filter(f => categorize(f) === activeCategory)
	);

	const vcpuOptions = $derived(
		[...new Set(categoryFiltered.map(f => f.vcpus))].sort((a, b) => a - b)
	);

	const ramOptions = $derived(
		[...new Set(categoryFiltered.map(f => f.ram))].sort((a, b) => a - b)
	);

	const gpuModelOptions = $derived(
		activeCategory === 'gpu'
			? [...new Set(categoryFiltered.map(f => extractGpuModel(f)))].sort()
			: []
	);

	const filteredFlavors = $derived(
		categoryFiltered
			.filter(f => filterVcpus === null || f.vcpus === filterVcpus)
			.filter(f => filterRam === null || f.ram === filterRam)
			.filter(f => filterGpu === null || extractGpuModel(f) === filterGpu)
	);

	function setCategory(cat: FlavorCategory) {
		activeCategory = cat;
		filterVcpus = null;
		filterRam = null;
		filterGpu = null;
	}

	function ramLabel(mb: number): string {
		return mb >= 1024 ? `${mb / 1024} GB` : `${mb} MB`;
	}
</script>

<!-- 카테고리 필터 탭 -->
<div class="flex gap-2 mb-3">
	{#each ([
		{ key: 'all', label: `전체 (${flavors.length})` },
		{ key: 'cpu', label: `CPU (${counts.cpu})` },
		{ key: 'gpu', label: `GPU (${counts.gpu})` },
		{ key: 'other', label: `기타 (${counts.other})` },
	] as const) as tab}
		<button
			onclick={() => setCategory(tab.key)}
			class="px-3 py-1 rounded-lg text-xs font-medium transition-colors {activeCategory === tab.key
				? 'bg-blue-600 text-white'
				: 'bg-gray-800 text-gray-400 hover:bg-gray-700'}"
		>{tab.label}</button>
	{/each}
</div>

<!-- vCPU / RAM 필터 -->
<div class="flex items-center gap-3 mb-4">
	<div class="flex items-center gap-1.5">
		<label class="text-xs text-gray-500">vCPU</label>
		<select
			value={filterVcpus}
			onchange={(e) => { const v = (e.target as HTMLSelectElement).value; filterVcpus = v === '' ? null : Number(v); }}
			class="bg-gray-800 border border-gray-600 rounded-lg px-2 py-1 text-xs text-white focus:outline-none focus:border-blue-500"
		>
			<option value="">전체</option>
			{#each vcpuOptions as v}
				<option value={v}>{v} vCPU</option>
			{/each}
		</select>
	</div>
	<div class="flex items-center gap-1.5">
		<label class="text-xs text-gray-500">RAM</label>
		<select
			value={filterRam}
			onchange={(e) => { const v = (e.target as HTMLSelectElement).value; filterRam = v === '' ? null : Number(v); }}
			class="bg-gray-800 border border-gray-600 rounded-lg px-2 py-1 text-xs text-white focus:outline-none focus:border-blue-500"
		>
			<option value="">전체</option>
			{#each ramOptions as r}
				<option value={r}>{ramLabel(r)}</option>
			{/each}
		</select>
	</div>
	{#if activeCategory === 'gpu'}
		<div class="flex items-center gap-1.5">
			<label class="text-xs text-gray-500">GPU</label>
			<select
				value={filterGpu}
				onchange={(e) => { const v = (e.target as HTMLSelectElement).value; filterGpu = v === '' ? null : v; }}
				class="bg-gray-800 border border-gray-600 rounded-lg px-2 py-1 text-xs text-white focus:outline-none focus:border-blue-500"
			>
				<option value="">전체</option>
				{#each gpuModelOptions as model}
					<option value={model}>{model}</option>
				{/each}
			</select>
		</div>
	{/if}
	<span class="text-xs text-gray-500 ml-auto">{filteredFlavors.length}개</span>
</div>

<!-- GPU 탭 활성 시 가용량 요약 배너 -->
{#if activeCategory === 'gpu' && gpuAvailability.length > 0}
	<div class="mb-3 p-3 rounded-lg bg-gray-800/60 border border-gray-700">
		<div class="text-xs text-gray-400 mb-2">GPU 가용량{#if selectedGpuRequest.size > 0} <span class="text-blue-400">(선택 flavor 반영)</span>{/if}</div>
		<div class="flex flex-wrap gap-2">
			{#each gpuAvailability as g}
				{@const requested = selectedGpuRequest.get(g.device_name) ?? 0}
				{@const effectiveAvail = g.available - requested}
				<span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs
					{effectiveAvail > 0
						? 'bg-green-900/30 text-green-300 border border-green-800/40'
						: requested > 0
							? 'bg-yellow-900/30 text-yellow-300 border border-yellow-800/40'
							: 'bg-red-900/30 text-red-300 border border-red-800/40'}">
					<span class="font-medium">{g.device_name}</span>
					{#if requested > 0}
						<span class="opacity-70">{effectiveAvail}/{g.total}</span>
						<span class="opacity-50 text-xs">(-{requested})</span>
					{:else}
						<span class="opacity-70">{g.available}/{g.total}</span>
					{/if}
				</span>
			{/each}
		</div>
	</div>
{/if}

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
