<script lang="ts">
	import type { ImageInfo } from '$lib/types/compute';

	let { images, selectedId, onSelect }: {
		images: ImageInfo[];
		selectedId: string | null;
		onSelect: (id: string, name: string) => void;
	} = $props();

	let activeDistro = $state<string | null>(null);
	let searchTerm = $state('');

	const distroLabels: Record<string, string> = {
		ubuntu: 'Ubuntu', centos: 'CentOS', rocky: 'Rocky Linux',
		debian: 'Debian', 'fedora-coreos': 'Fedora CoreOS', fedora: 'Fedora', rhel: 'RHEL',
		windows: 'Windows', cirros: 'CirrOS',
	};

	const distroColors: Record<string, string> = {
		ubuntu: 'bg-orange-600', centos: 'bg-purple-600', rocky: 'bg-green-600',
		debian: 'bg-red-600', fedora: 'bg-blue-600', 'fedora-coreos': 'bg-blue-700',
		rhel: 'bg-red-700', windows: 'bg-sky-600', cirros: 'bg-teal-600',
	};

	const distroLogos: Record<string, string> = {
		ubuntu: '/logos/Ubuntu.png',
		centos: '/logos/CentOS.png',
		fedora: '/logos/Fedora.png',
		'fedora-coreos': '/logos/coreos.png',
		cirros: '/logos/Cirros.png',
		windows: '/logos/Windows.png',
	};

	function logoPath(distro: string | null): string | null {
		return distroLogos[distro ?? ''] ?? null;
	}

	const distros = $derived(
		[...new Set(images.map(i => i.os_distro ?? '기타'))].sort((a, b) => {
			if (a === '기타') return 1;
			if (b === '기타') return -1;
			return a.localeCompare(b);
		})
	);

	// filtered by distro chip then by search term
	const distroFiltered = $derived(
		activeDistro === null
			? images
			: images.filter(i => (i.os_distro ?? '기타') === activeDistro)
	);

	const filteredImages = $derived(
		searchTerm.trim()
			? distroFiltered.filter(i =>
				i.name.toLowerCase().includes(searchTerm.trim().toLowerCase()) ||
				(i.os_distro ?? '').toLowerCase().includes(searchTerm.trim().toLowerCase())
			)
			: distroFiltered
	);

	function distroLabel(d: string): string {
		return distroLabels[d] ?? d;
	}

	function avatarLetter(name: string): string {
		return name.charAt(0).toUpperCase();
	}

	function avatarColor(distro: string | null): string {
		return distroColors[distro ?? ''] ?? 'bg-gray-600';
	}

	function formatDate(dateStr: string | null): string {
		if (!dateStr) return '';
		return dateStr.slice(0, 10);
	}

	function distroDescription(img: ImageInfo): string {
		const parts: string[] = [];
		const label = distroLabels[img.os_distro ?? ''] ?? '';
		if (label) {
			const m = img.name.match(/(\d{2}\.\d{2})/);
			if (m) parts.push(`${label} ${m[1]} LTS`);
			else parts.push(label);
		}
		if (img.os_type) parts.push(img.os_type);
		return parts.join(' · ') || img.name;
	}
</script>

<!-- 검색바 -->
<div class="relative mb-4">
	<span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none">
		<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
			<circle cx="11" cy="11" r="7"/>
			<path stroke-linecap="round" stroke-linejoin="round" d="m21 21-4.3-4.3"/>
		</svg>
	</span>
	<input
		type="search"
		bind:value={searchTerm}
		placeholder="이미지명, OS, 버전으로 검색…"
		class="w-full bg-gray-900 border border-gray-800 text-gray-200 rounded-lg pl-9 pr-3 py-2 text-sm outline-none focus:border-gray-600 placeholder-gray-600"
	/>
</div>

<!-- OS family 칩 -->
<div class="flex flex-wrap gap-2 mb-5">
	<button
		onclick={() => activeDistro = null}
		class="inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-medium transition-all {activeDistro === null
			? 'bg-blue-600 text-white'
			: 'bg-gray-800 text-gray-400 hover:bg-gray-700'}"
	>전체 <span class="opacity-70 font-mono text-[10.5px]">{images.length}</span></button>
	{#each distros as d}
		{@const count = images.filter(i => (i.os_distro ?? '기타') === d).length}
		<button
			onclick={() => activeDistro = d}
			class="inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-medium transition-all {activeDistro === d
				? 'bg-blue-600 text-white'
				: 'bg-gray-800 text-gray-400 hover:bg-gray-700'}"
		>{distroLabel(d)} <span class="opacity-70 font-mono text-[10.5px]">{count}</span></button>
	{/each}
</div>

<!-- 이미지 카드 그리드 -->
<div class="grid grid-cols-1 @lg/panel:grid-cols-2 @3xl/panel:grid-cols-3 gap-3">
	{#each filteredImages as img}
		<button
			onclick={() => onSelect(img.id, img.name)}
			class="relative text-left p-4 rounded-xl border transition-all hover:-translate-y-px hover:shadow-md {selectedId === img.id
				? 'border-blue-500 bg-blue-900/20 ring-1 ring-blue-500/30'
				: 'border-gray-700 bg-gray-900 hover:border-gray-500'}"
		>
			<!-- 선택 체크마크 (우측 상단 pill) -->
			{#if selectedId === img.id}
				<div class="absolute top-3.5 right-3.5 w-5 h-5 bg-blue-600 rounded-full flex items-center justify-center">
					<svg class="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"/>
					</svg>
				</div>
			{/if}

			<!-- 아바타 + 이름 -->
			<div class="flex items-start gap-3 mb-2">
				{#if logoPath(img.os_distro ?? null)}
					<img
						src={logoPath(img.os_distro ?? null)}
						alt={img.os_distro ?? ''}
						class="w-9 h-9 rounded-lg object-contain bg-gray-800 border border-gray-700 p-0.5 flex-shrink-0"
					/>
				{:else}
					<div class="w-9 h-9 rounded-lg {avatarColor(img.os_distro ?? null)} flex items-center justify-center text-white text-sm font-bold flex-shrink-0 border border-white/10">
						{avatarLetter(img.name)}
					</div>
				{/if}
				<div class="min-w-0 flex-1">
					<div class="font-semibold text-white text-[13.5px] font-mono truncate leading-tight">{img.name}</div>
					<div class="text-[11px] text-gray-500 truncate mt-0.5">{distroDescription(img)}</div>
				</div>
			</div>

			<!-- 메타 -->
			<div class="flex items-center gap-2 text-[11px] text-gray-500 font-mono pt-2 mt-2 border-t border-gray-800">
				{#if img.disk_format}
					<span class="px-1.5 py-0.5 bg-gray-800 border border-gray-700 rounded text-gray-400 text-[10px] lowercase">{img.disk_format}</span>
				{/if}
				{#if img.min_disk}
					<span>{img.min_disk} GB</span>
				{/if}
				{#if img.created_at}
					<span class="ml-auto">{formatDate(img.created_at)}</span>
				{/if}
			</div>
		</button>
	{/each}

	{#if filteredImages.length === 0}
		<div class="col-span-3 text-center py-10 text-gray-600 text-sm">
			조건에 맞는 이미지가 없습니다
		</div>
	{/if}
</div>
