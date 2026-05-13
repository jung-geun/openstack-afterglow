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

	interface QuotaPair { limit: number; in_use: number; }
	interface FlavorQuotaSummary {
		instances?: QuotaPair;
		cores?: QuotaPair;
		ram?: QuotaPair;       // MB
		gigabytes?: QuotaPair; // GB
	}

	let { flavors, selectedId, onSelect, quota }: {
		flavors: FlavorInfo[];
		selectedId: string | null;
		onSelect: (id: string, name: string) => void;
		quota?: FlavorQuotaSummary | null;
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
		const norm = (s: string) => s.replace(/[\s\-_.]+/g, '').toLowerCase();
		for (const r of parseGpuRequest(f)) {
			const reqNorm = norm(r.model);
			const matched = gpuAvailability.find(g => {
				const devNorm = norm(g.device_name);
				return devNorm.includes(reqNorm) || reqNorm.includes(devNorm);
			});
			if (matched) {
				map.set(matched.device_name, (map.get(matched.device_name) ?? 0) + r.count);
			}
		}
		return map;
	})());

	type FlavorCategory = 'all' | 'general' | 'cpu' | 'memory' | 'gpu';
	let activeCategory = $state<FlavorCategory>('all');
	let searchTerm = $state('');
	let currentPage = $state(1);
	const PAGE_SIZE = 10;

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

	const searchedFlavors = $derived(
		searchTerm.trim()
			? filteredFlavors.filter(f =>
				f.name.toLowerCase().includes(searchTerm.trim().toLowerCase()) ||
				String(f.vcpus).includes(searchTerm.trim()) ||
				ramLabel(f.ram).toLowerCase().includes(searchTerm.trim().toLowerCase())
			)
			: filteredFlavors
	);

	const totalPages = $derived(Math.max(1, Math.ceil(searchedFlavors.length / PAGE_SIZE)));

	const paginatedFlavors = $derived(
		searchedFlavors.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE)
	);

	$effect(() => {
		activeCategory;
		searchTerm;
		currentPage = 1;
	});

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

	function quotaRemaining(p?: QuotaPair): number {
		if (!p) return -1;
		if (p.limit < 0) return -1;
		return Math.max(0, p.limit - p.in_use);
	}

	function quotaText(p?: QuotaPair, suffix = ''): string {
		if (!p) return '-';
		if (p.limit < 0) return '∞';
		return `${Math.max(0, p.limit - p.in_use)}${suffix}`;
	}

	function quotaTitle(p?: QuotaPair, label = ''): string {
		if (!p) return label;
		const limit = p.limit < 0 ? '∞' : p.limit;
		return `${label} 사용 ${p.in_use} / ${limit}`;
	}

	const selectedFlavor = $derived(flavors.find(f => f.id === selectedId));

	const flavorChipClass = (remaining: number, requested: number) => {
		if (remaining < 0) return 'bg-gray-800/60 text-gray-300 border border-gray-700';
		if (requested > 0 && remaining - requested < 0) return 'bg-red-900/40 text-red-300 border border-red-800/50';
		if (remaining === 0) return 'bg-red-900/40 text-red-300 border border-red-800/50';
		if (requested > 0) return 'bg-yellow-900/30 text-yellow-300 border border-yellow-800/40';
		return 'bg-green-900/30 text-green-300 border border-green-800/40';
	};

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

<!-- 통합 검색 -->
<div class="relative mb-4">
	<span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none">
		<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
			<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z"/>
		</svg>
	</span>
	<input
		type="search"
		placeholder="플레이버 이름, vCPU, RAM으로 검색..."
		bind:value={searchTerm}
		class="w-full bg-gray-900 border border-gray-800 text-gray-200 rounded-lg pl-9 pr-3 py-2 text-sm outline-none focus:border-gray-600 placeholder-gray-600"
	/>
</div>

<!-- 프로젝트 quota 배너 -->
{#if quota}
	{@const reqVm = selectedFlavor ? 1 : 0}
	{@const reqCpu = selectedFlavor?.vcpus ?? 0}
	{@const reqRamMb = selectedFlavor?.ram ?? 0}
	{@const reqDiskGb = selectedFlavor?.disk ?? 0}
	{@const remVm = quotaRemaining(quota.instances)}
	{@const remCpu = quotaRemaining(quota.cores)}
	{@const remRamMb = quotaRemaining(quota.ram)}
	{@const remDiskGb = quotaRemaining(quota.gigabytes)}
	<div class="mb-4 p-3 rounded-lg bg-gray-800/60 border border-gray-700">
		<div class="text-xs text-gray-400 mb-2">
			프로젝트 잔여 quota
			{#if selectedFlavor}<span class="text-blue-400">(선택 flavor 반영)</span>{/if}
		</div>
		<div class="flex flex-wrap gap-2">
			<span
				class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs {flavorChipClass(remVm, reqVm)}"
				title={quotaTitle(quota.instances, 'VM 인스턴스')}
			>
				<span class="font-medium">VM</span>
				{#if reqVm > 0 && remVm >= 0}
					<span class="opacity-70">{remVm - reqVm}/{quota.instances?.limit}</span>
					<span class="opacity-50">(-{reqVm})</span>
				{:else}
					<span class="opacity-70">{quotaText(quota.instances)}</span>
				{/if}
			</span>
			<span
				class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs {flavorChipClass(remCpu, reqCpu)}"
				title={quotaTitle(quota.cores, 'vCPU')}
			>
				<span class="font-medium">vCPU</span>
				{#if reqCpu > 0 && remCpu >= 0}
					<span class="opacity-70">{remCpu - reqCpu}/{quota.cores?.limit}</span>
					<span class="opacity-50">(-{reqCpu})</span>
				{:else}
					<span class="opacity-70">{quotaText(quota.cores)}</span>
				{/if}
			</span>
			<span
				class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs {flavorChipClass(remRamMb, reqRamMb)}"
				title={quotaTitle(quota.ram, 'RAM (MB)')}
			>
				<span class="font-medium">RAM</span>
				{#if reqRamMb > 0 && remRamMb >= 0}
					<span class="opacity-70">{Math.floor((remRamMb - reqRamMb) / 1024)}GB / {Math.floor((quota.ram?.limit ?? 0) / 1024)}GB</span>
					<span class="opacity-50">(-{reqRamMb >= 1024 ? Math.round(reqRamMb / 1024) + 'GB' : reqRamMb + 'MB'})</span>
				{:else if remRamMb < 0}
					<span class="opacity-70">∞</span>
				{:else}
					<span class="opacity-70">{Math.floor(remRamMb / 1024)}GB</span>
				{/if}
			</span>
			<span
				class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs {flavorChipClass(remDiskGb, reqDiskGb)}"
				title={quotaTitle(quota.gigabytes, '볼륨 디스크 (GB)')}
			>
				<span class="font-medium">DISK</span>
				{#if reqDiskGb > 0 && remDiskGb >= 0}
					<span class="opacity-70">{remDiskGb - reqDiskGb}GB / {quota.gigabytes?.limit}GB</span>
					<span class="opacity-50">(-{reqDiskGb}GB)</span>
				{:else if remDiskGb < 0}
					<span class="opacity-70">∞</span>
				{:else}
					<span class="opacity-70">{remDiskGb}GB</span>
				{/if}
			</span>
		</div>
	</div>
{/if}

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
	{#each paginatedFlavors as flavor}
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

	{#if searchedFlavors.length === 0}
		<div class="text-center py-8 text-gray-600 text-sm">조건에 맞는 플레이버가 없습니다</div>
	{/if}
</div>

<!-- 페이지네이션 -->
{#if totalPages > 1}
<div class="flex items-center justify-between mt-3 text-xs text-gray-500">
	<span>{searchedFlavors.length}개 중 {(currentPage - 1) * PAGE_SIZE + 1}–{Math.min(currentPage * PAGE_SIZE, searchedFlavors.length)}</span>
	<div class="flex gap-1">
		<button
			onclick={() => currentPage = Math.max(1, currentPage - 1)}
			disabled={currentPage === 1}
			class="px-2 py-1 rounded bg-gray-800 text-gray-400 hover:bg-gray-700 disabled:opacity-30 disabled:cursor-not-allowed"
		>이전</button>
		{#each Array.from({ length: totalPages }, (_, i) => i + 1) as p}
			<button
				onclick={() => currentPage = p}
				class="px-2 py-1 rounded {p === currentPage ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'}"
			>{p}</button>
		{/each}
		<button
			onclick={() => currentPage = Math.min(totalPages, currentPage + 1)}
			disabled={currentPage === totalPages}
			class="px-2 py-1 rounded bg-gray-800 text-gray-400 hover:bg-gray-700 disabled:opacity-30 disabled:cursor-not-allowed"
		>다음</button>
	</div>
</div>
{/if}
