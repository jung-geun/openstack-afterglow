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
		is_public: boolean;
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

	type FlavorCategory = 'all' | 'general' | 'cpu' | 'memory' | 'gpu';
	let activeCategory = $state<FlavorCategory>('all');

	function hasGpu(flavor: FlavorInfo): boolean {
		return Object.keys(flavor.extra_specs).some(
			(k) => k.toLowerCase().includes('gpu') || k.toLowerCase().includes('pci')
		);
	}

	function categorize(f: FlavorInfo): 'general' | 'cpu' | 'memory' | 'gpu' {
		if (f.name.startsWith('gpu.') || hasGpu(f)) return 'gpu';
		if (f.name.startsWith('c1.') || f.name.startsWith('cpu.')) return 'cpu';
		if (f.name.startsWith('r1.') || f.name.startsWith('mem.')) return 'memory';
		return 'general';
	}

	const counts = $derived({
		general: flavors.filter(f => categorize(f) === 'general').length,
		cpu: flavors.filter(f => categorize(f) === 'cpu').length,
		memory: flavors.filter(f => categorize(f) === 'memory').length,
		gpu: flavors.filter(f => categorize(f) === 'gpu').length,
	});

	const filteredFlavors = $derived(
		activeCategory === 'all'
			? flavors
			: flavors.filter(f => categorize(f) === activeCategory)
	);

	function ramLabel(mb: number): string {
		return mb >= 1024 ? `${Math.round(mb / 1024)} GB` : `${mb} MB`;
	}

	function categoryBadge(f: FlavorInfo): { label: string; class: string } | null {
		const cat = categorize(f);
		if (cat === 'gpu') return { label: 'GPU', class: 'bg-purple-900/50 text-purple-300 border-purple-700/50' };
		if (cat === 'cpu') return { label: 'CPU', class: 'bg-sky-900/50 text-sky-300 border-sky-700/50' };
		if (cat === 'memory') return { label: '메모리', class: 'bg-amber-900/50 text-amber-300 border-amber-700/50' };
		return null;
	}

	function gpuSummary(f: FlavorInfo): string {
		const reqs = parseGpuRequest(f);
		if (reqs.length === 0) return '';
		return reqs.map(r => `${r.model} × ${r.count}`).join(', ');
	}

	function networkBandwidth(f: FlavorInfo): string {
		const bw = f.extra_specs?.['quota:vif_outbound_peak'] ?? f.extra_specs?.['hw:bandwidth'] ?? '';
		if (bw) return `${bw} Gbps`;
		// Estimate from vCPU count
		if (f.vcpus >= 32) return '25 Gbps';
		if (f.vcpus >= 16) return '10 Gbps';
		if (f.vcpus >= 8) return '5 Gbps';
		if (f.vcpus >= 4) return '2.5 Gbps';
		return '1 Gbps';
	}
</script>

<p class="text-sm text-gray-400 mb-4">
	현재 프로젝트 쿼터 내 생성 가능한 플레이버만 표시합니다. GPU 플레이버는 스케줄러가 가용 호스트를 자동 선택합니다.
</p>

<!-- 카테고리 필터 탭 -->
<div class="flex gap-2 mb-4">
	{#each ([
		{ key: 'all', label: `전체 (${flavors.length})` },
		{ key: 'general', label: `범용 (${counts.general})` },
		{ key: 'cpu', label: `CPU (${counts.cpu})` },
		{ key: 'memory', label: `메모리 (${counts.memory})` },
		{ key: 'gpu', label: `GPU (${counts.gpu})` },
	] as const) as tab}
		<button
			onclick={() => { activeCategory = tab.key; }}
			class="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors {activeCategory === tab.key
				? 'bg-blue-600 text-white'
				: 'bg-gray-800 text-gray-400 hover:bg-gray-700'}"
		>{tab.label}</button>
	{/each}
</div>

<!-- GPU 가용량 배너 -->
{#if gpuAvailability.length > 0 && (activeCategory === 'all' || activeCategory === 'gpu')}
	<div class="mb-4 p-3 rounded-lg bg-gray-800/60 border border-gray-700">
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

<!-- 플레이버 테이블 -->
<div class="bg-[#0B1220] border border-gray-800 rounded-xl overflow-hidden">
	<!-- 테이블 헤더 -->
	<div class="grid grid-cols-[2fr_80px_90px_100px_100px] px-4 py-2.5 border-b border-gray-800 text-[11px] uppercase tracking-wider text-gray-500 font-medium">
		<div>이름</div>
		<div class="text-center">VCPU</div>
		<div class="text-center">RAM</div>
		<div class="text-center">디스크(SSD)</div>
		<div class="text-center">네트워크</div>
	</div>

	<!-- 테이블 바디 -->
	{#each filteredFlavors as flavor}
		{@const badge = categoryBadge(flavor)}
		{@const gpu = gpuSummary(flavor)}
		<button
			onclick={() => onSelect(flavor.id, flavor.name)}
			class="w-full grid grid-cols-[2fr_80px_90px_100px_100px] px-4 py-3 border-b border-gray-800/60 text-sm transition-all hover:bg-gray-800/40
				{selectedId === flavor.id ? 'bg-blue-900/20 border-l-2 border-l-blue-500' : ''}"
		>
			<div class="flex items-center gap-3 min-w-0">
				<div class="w-8 h-8 rounded-lg bg-gray-800 border border-gray-700 flex items-center justify-center flex-shrink-0">
					<svg class="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z"/>
					</svg>
				</div>
				<div class="min-w-0">
					<div class="flex items-center gap-2">
						<span class="font-medium text-white truncate">{flavor.name}</span>
						{#if badge}
							<span class="px-1.5 py-0.5 rounded text-[10px] border {badge.class}">{badge.label}</span>
						{/if}
						{#if flavor.is_public}
							<span class="px-1.5 py-0.5 rounded text-[10px] bg-gray-800 text-gray-400 border border-gray-700">공용</span>
						{/if}
					</div>
					{#if gpu}
						<div class="text-[11px] text-purple-400 mt-0.5">{gpu}</div>
					{/if}
				</div>
			</div>
			<div class="text-center text-gray-300 self-center">{flavor.vcpus}</div>
			<div class="text-center text-gray-300 self-center">{ramLabel(flavor.ram)}</div>
			<div class="text-center text-gray-300 self-center">{flavor.disk} GB</div>
			<div class="text-center text-gray-400 self-center text-xs">{networkBandwidth(flavor)}</div>
		</button>
	{/each}

	{#if filteredFlavors.length === 0}
		<div class="text-center py-8 text-gray-600 text-sm">조건에 맞는 플레이버가 없습니다</div>
	{/if}
</div>
