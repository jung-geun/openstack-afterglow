<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api/client';
	import { auth } from '$lib/stores/auth';
	import type { FlavorOption as FlavorInfo } from '$lib/types/flavor';

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
				'/api/v1/dashboard/gpu-available', token, projectId
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
			// 정규화 후 정확히 일치하는 device를 찾는다.
			// includes() 비교는 "rtx3060lhr".includes("rtx3060") = true 가 되어
			// RTX 3060 alias가 RTX 3060 LHR device와 잘못 매칭되는 버그가 있었다.
			const matched = gpuAvailability.find(g => norm(g.device_name) === reqNorm);
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
		return Object.keys(flavor.extra_specs ?? {}).some(
			(k) => k.toLowerCase().includes('gpu') || k.startsWith('pci_passthrough')
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

<div class="flex flex-col">
<p class="order-2 mb-4 hidden text-sm text-gray-400 md:block">
	현재 프로젝트 쿼터 내 생성 가능한 플레이버만 표시합니다. GPU 플레이버는 스케줄러가 가용 호스트를 자동 선택합니다.
</p>

<!-- 카테고리 필터 탭 -->
<div class="order-3 mb-4 flex flex-wrap gap-2">
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
<div class="order-4 relative mb-4">
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

<!-- 프로젝트 quota delta 미터 -->
{#if quota}
	{@const reqVm = selectedFlavor ? 1 : 0}
	{@const reqCpu = selectedFlavor?.vcpus ?? 0}
	{@const reqRamMb = selectedFlavor?.ram ?? 0}
	{@const reqDiskGb = selectedFlavor?.disk ?? 0}
	{@const limVm = quota.instances?.limit ?? -1}
	{@const limCpu = quota.cores?.limit ?? -1}
	{@const limRamMb = quota.ram?.limit ?? -1}
	{@const limDiskGb = quota.gigabytes?.limit ?? -1}
	{@const curVm = quota.instances?.in_use ?? 0}
	{@const curCpu = quota.cores?.in_use ?? 0}
	{@const curRamMb = quota.ram?.in_use ?? 0}
	{@const curDiskGb = quota.gigabytes?.in_use ?? 0}
	{@const critVm = limVm >= 0 && curVm + reqVm > limVm}
	{@const critCpu = limCpu >= 0 && curCpu + reqCpu > limCpu}
	{@const critRam = limRamMb >= 0 && curRamMb + reqRamMb > limRamMb}
	{@const critDisk = limDiskGb >= 0 && curDiskGb + reqDiskGb > limDiskGb}
	<div class="order-1 mb-4 overflow-hidden rounded-xl border border-gray-800 bg-gray-900/70 md:mb-5">
		<div class="flex items-center justify-between px-3 py-2 border-b border-gray-800">
			<span class="text-[11px] text-gray-400 font-medium">
				프로젝트 잔여 쿼터
				{#if selectedFlavor}<span class="text-blue-400 ml-1">— 선택 flavor 반영</span>{/if}
			</span>
			<div class="hidden items-center gap-3 text-[10px] text-gray-500 @md/panel:flex">
				<span class="flex items-center gap-1"><i class="inline-block w-2 h-2 rounded-full bg-gray-500"></i>현재 사용</span>
				<span class="flex items-center gap-1"><i class="inline-block w-2 h-2 rounded-full bg-blue-500"></i>이번 VM 추가</span>
			</div>
		</div>
		<div class="grid grid-cols-2 gap-px bg-gray-800 @2xl/panel:grid-cols-4">
			<!-- VM cell -->
			<div class="flex flex-col gap-1.5 bg-gray-900 px-3 py-2">
				<span class="text-[10px] uppercase tracking-wider text-gray-500 font-mono font-semibold">VM</span>
				<div class="flex items-baseline gap-1 font-mono">
					<span class="text-sm text-gray-300">{curVm}</span>
					{#if reqVm > 0}
						<span class="text-gray-600 text-[10px]">→</span>
						<span class="text-sm font-bold {critVm ? 'text-red-400' : 'text-blue-400'}">{curVm + reqVm}</span>
					{/if}
					{#if limVm >= 0}<span class="text-gray-500 text-[11px]">/ {limVm}</span>{/if}
				</div>
				{#if limVm >= 0}
					{@const curPct = Math.min(100, (curVm / limVm) * 100)}
					{@const deltaPct = Math.min(100 - curPct, (reqVm / limVm) * 100)}
					<div class="relative h-[5px] rounded-full bg-gray-800 overflow-hidden">
						<div class="absolute left-0 top-0 h-full bg-gray-500 rounded-full" style="width:{curPct}%"></div>
						<div class="absolute top-0 h-full rounded-r-full {critVm ? 'bg-red-500' : 'bg-blue-500'}" style="left:{curPct}%; width:{deltaPct}%"></div>
					</div>
				{/if}
			</div>
			<!-- vCPU cell -->
			<div class="flex flex-col gap-1.5 bg-gray-900 px-3 py-2">
				<span class="text-[10px] uppercase tracking-wider text-gray-500 font-mono font-semibold">vCPU</span>
				<div class="flex items-baseline gap-1 font-mono">
					<span class="text-sm text-gray-300">{curCpu}</span>
					{#if reqCpu > 0}
						<span class="text-gray-600 text-[10px]">→</span>
						<span class="text-sm font-bold {critCpu ? 'text-red-400' : 'text-blue-400'}">{curCpu + reqCpu}</span>
					{/if}
					{#if limCpu >= 0}<span class="text-gray-500 text-[11px]">/ {limCpu}</span>{/if}
				</div>
				{#if limCpu >= 0}
					{@const curPct = Math.min(100, (curCpu / limCpu) * 100)}
					{@const deltaPct = Math.min(100 - curPct, (reqCpu / limCpu) * 100)}
					<div class="relative h-[5px] rounded-full bg-gray-800 overflow-hidden">
						<div class="absolute left-0 top-0 h-full bg-gray-500 rounded-full" style="width:{curPct}%"></div>
						<div class="absolute top-0 h-full rounded-r-full {critCpu ? 'bg-red-500' : 'bg-blue-500'}" style="left:{curPct}%; width:{deltaPct}%"></div>
					</div>
				{/if}
			</div>
			<!-- RAM cell -->
			<div class="flex flex-col gap-1.5 bg-gray-900 px-3 py-2">
				<span class="text-[10px] uppercase tracking-wider text-gray-500 font-mono font-semibold">RAM</span>
				<div class="flex items-baseline gap-1 font-mono">
					<span class="text-sm text-gray-300">{Math.round(curRamMb / 1024)}GB</span>
					{#if reqRamMb > 0}
						<span class="text-gray-600 text-[10px]">→</span>
						<span class="text-sm font-bold {critRam ? 'text-red-400' : 'text-blue-400'}">{Math.round((curRamMb + reqRamMb) / 1024)}GB</span>
					{/if}
					{#if limRamMb >= 0}<span class="text-gray-500 text-[11px]">/ {Math.round(limRamMb / 1024)}GB</span>{/if}
				</div>
				{#if limRamMb >= 0}
					{@const curPct = Math.min(100, (curRamMb / limRamMb) * 100)}
					{@const deltaPct = Math.min(100 - curPct, (reqRamMb / limRamMb) * 100)}
					<div class="relative h-[5px] rounded-full bg-gray-800 overflow-hidden">
						<div class="absolute left-0 top-0 h-full bg-gray-500 rounded-full" style="width:{curPct}%"></div>
						<div class="absolute top-0 h-full rounded-r-full {critRam ? 'bg-red-500' : 'bg-blue-500'}" style="left:{curPct}%; width:{deltaPct}%"></div>
					</div>
				{/if}
			</div>
			<!-- DISK cell -->
			<div class="flex flex-col gap-1.5 bg-gray-900 px-3 py-2">
				<span class="text-[10px] uppercase tracking-wider text-gray-500 font-mono font-semibold">DISK</span>
				{#if limDiskGb < 0}
					<div class="flex items-baseline gap-1 font-mono">
						<span class="text-sm text-gray-300">{curDiskGb}GB</span>
						<span class="text-gray-500 text-[11px]">/ ∞</span>
					</div>
					<div class="relative h-[5px] rounded-full bg-gray-800 overflow-hidden">
						<div class="absolute left-0 top-0 h-full bg-gray-500 rounded-full" style="width:0%"></div>
					</div>
				{:else}
					<div class="flex items-baseline gap-1 font-mono">
						<span class="text-sm text-gray-300">{curDiskGb}GB</span>
						{#if reqDiskGb > 0}
							<span class="text-gray-600 text-[10px]">→</span>
							<span class="text-sm font-bold {critDisk ? 'text-red-400' : 'text-blue-400'}">{curDiskGb + reqDiskGb}GB</span>
						{/if}
						<span class="text-gray-500 text-[11px]">/ {limDiskGb}GB</span>
					</div>
					{@const curPct = Math.min(100, (curDiskGb / limDiskGb) * 100)}
					{@const deltaPct = Math.min(100 - curPct, (reqDiskGb / limDiskGb) * 100)}
					<div class="relative h-[5px] rounded-full bg-gray-800 overflow-hidden">
						<div class="absolute left-0 top-0 h-full bg-gray-500 rounded-full" style="width:{curPct}%"></div>
						<div class="absolute top-0 h-full rounded-r-full {critDisk ? 'bg-red-500' : 'bg-blue-500'}" style="left:{curPct}%; width:{deltaPct}%"></div>
					</div>
				{/if}
			</div>
		</div>
	</div>
{/if}

<!-- GPU 가용량 배너 -->
{#if gpuAvailability.length > 0 && (activeCategory === 'all' || activeCategory === 'gpu')}
	<div class="order-5 mb-4 rounded-lg border border-gray-700 bg-gray-800/60 p-3">
		<div class="text-xs text-gray-400 mb-2">GPU 가용량{#if selectedGpuRequest.size > 0} <span class="text-blue-400">(선택 flavor 반영)</span>{/if}</div>
		<div class="flex flex-wrap gap-2">
			{#each gpuAvailability as g}
				{@const requested = selectedGpuRequest.get(g.device_name) ?? 0}
				{@const nextUsed = g.used + requested}
				{@const avail = g.total - nextUsed}
				<span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full font-mono text-[11.5px]
					{avail > 0 && requested === 0
						? 'bg-green-900/30 text-green-300 border border-green-800/40'
						: avail >= 0 && requested > 0
							? 'bg-blue-900/30 text-blue-300 border border-blue-800/40'
							: 'bg-red-900/30 text-red-300 border border-red-800/40'}">
					<b class="font-semibold">{g.device_name}</b>
					{#if requested > 0}
						<span class="opacity-70">{g.used}/{g.total}</span>
						<span class="text-[10px] opacity-50">→</span>
						<span class="font-bold text-blue-400">{nextUsed}/{g.total}</span>
					{:else}
						<span class="opacity-70">{g.used}/{g.total}</span>
					{/if}
				</span>
			{/each}
		</div>
	</div>
{/if}

<!-- 모바일 플레이버 카드: 가로 스크롤 없이 이름과 핵심 스펙을 함께 표시한다. -->
<div class="order-6 space-y-2 @2xl/panel:hidden">
	{#each paginatedFlavors as flavor}
		{@const badge = categoryBadge(flavor)}
		{@const gpu = gpuSummary(flavor)}
		<button
			onclick={() => onSelect(flavor.id, flavor.name)}
			aria-label={`${flavor.name} 플레이버 선택`}
			class="w-full rounded-xl border p-3 text-left transition-colors {selectedId === flavor.id
				? 'border-[var(--color-accent)] bg-[var(--color-accent)]/10 ring-1 ring-[var(--color-accent)]/30'
				: 'border-[var(--color-line)] bg-[var(--color-surface-raised)] hover:border-[var(--color-line-2)]'}"
		>
			<div class="flex items-start gap-3">
				<div class="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg border border-[var(--color-line)] bg-[var(--color-surface-sunken)]">
					<svg class="h-4 w-4 text-[var(--color-ink-2)]" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z"/>
					</svg>
				</div>
				<div class="min-w-0 flex-1">
					<div class="break-words font-mono text-sm font-semibold text-[var(--color-ink-0)]">{flavor.name}</div>
					<div class="mt-1 flex flex-wrap gap-1.5">
						{#if badge}
							<span class="rounded border px-1.5 py-0.5 text-[10px] {badge.class}">{badge.label}</span>
						{/if}
						{#if flavor.is_public}
							<span class="rounded border border-[var(--color-line)] bg-[var(--color-surface-sunken)] px-1.5 py-0.5 text-[10px] text-[var(--color-ink-2)]">공용</span>
						{/if}
						<span class="text-xs text-[var(--color-ink-3)]">{networkBandwidth(flavor)}</span>
					</div>
				</div>
			</div>
			<dl class="mt-3 grid grid-cols-3 gap-2 border-t border-[var(--color-line)] pt-2.5 font-mono">
				<div>
					<dt class="text-[10px] uppercase tracking-wide text-[var(--color-ink-3)]">vCPU</dt>
					<dd class="mt-0.5 text-sm text-[var(--color-ink-1)]">{flavor.vcpus}</dd>
				</div>
				<div>
					<dt class="text-[10px] uppercase tracking-wide text-[var(--color-ink-3)]">RAM</dt>
					<dd class="mt-0.5 text-sm text-[var(--color-ink-1)]">{ramLabel(flavor.ram)}</dd>
				</div>
				<div>
					<dt class="text-[10px] uppercase tracking-wide text-[var(--color-ink-3)]">Disk</dt>
					<dd class="mt-0.5 text-sm text-[var(--color-ink-1)]">{flavor.disk} GB</dd>
				</div>
			</dl>
			{#if gpu}
				<div class="mt-2 text-xs text-[var(--color-accent-2)]">{gpu}</div>
			{/if}
		</button>
	{/each}
	{#if searchedFlavors.length === 0}
		<div class="py-8 text-center text-sm text-[var(--color-ink-3)]">조건에 맞는 플레이버가 없습니다</div>
	{/if}
</div>

<!-- 데스크톱에서는 스펙 비교를 위한 표를 유지한다. -->
<div class="order-6 hidden overflow-hidden rounded-xl border border-gray-800 bg-[#0B1220] @2xl/panel:block">
	<div class="grid grid-cols-[2fr_80px_90px_100px_100px] border-b border-gray-800 px-4 py-2.5 text-[11px] font-medium uppercase tracking-wider text-gray-500">
		<div>이름</div>
		<div class="text-center">VCPU</div>
		<div class="text-center">RAM</div>
		<div class="text-center">디스크(SSD)</div>
		<div class="text-center">네트워크</div>
	</div>

	{#each paginatedFlavors as flavor}
		{@const badge = categoryBadge(flavor)}
		{@const gpu = gpuSummary(flavor)}
		<button
			onclick={() => onSelect(flavor.id, flavor.name)}
			class="grid w-full grid-cols-[2fr_80px_90px_100px_100px] border-b border-gray-800/60 px-4 py-3 text-sm transition-all hover:bg-gray-800/40
				{selectedId === flavor.id ? 'border-l-2 border-l-blue-500 bg-blue-900/20' : ''}"
		>
			<div class="flex min-w-0 items-center gap-3">
				<div class="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg border border-gray-700 bg-gray-800">
					<svg class="h-4 w-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 002 2v10a2 2 0 00-2 2zM9 9h6v6H9V9z"/>
					</svg>
				</div>
				<div class="min-w-0">
					<div class="flex items-center gap-2">
						<span class="truncate font-medium text-white">{flavor.name}</span>
						{#if badge}
							<span class="rounded border px-1.5 py-0.5 text-[10px] {badge.class}">{badge.label}</span>
						{/if}
						{#if flavor.is_public}
							<span class="rounded border border-gray-700 bg-gray-800 px-1.5 py-0.5 text-[10px] text-gray-400">공용</span>
						{/if}
					</div>
					{#if gpu}
						<div class="mt-0.5 text-[11px] text-purple-400">{gpu}</div>
					{/if}
				</div>
			</div>
			<div class="self-center text-center text-gray-300">{flavor.vcpus}</div>
			<div class="self-center text-center text-gray-300">{ramLabel(flavor.ram)}</div>
			<div class="self-center text-center text-gray-300">{flavor.disk} GB</div>
			<div class="self-center text-center text-xs text-gray-400">{networkBandwidth(flavor)}</div>
		</button>
	{/each}

	{#if searchedFlavors.length === 0}
		<div class="py-8 text-center text-sm text-gray-600">조건에 맞는 플레이버가 없습니다</div>
	{/if}
</div>

<!-- 페이지네이션 -->
{#if totalPages > 1}
<div class="order-7 mt-3 flex items-center justify-between text-xs text-gray-500">
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
</div>
