<script lang="ts">
	interface ImageInfo {
		id: string;
		name: string;
		status: string;
		min_disk: number;
		min_ram: number;
		disk_format: string | null;
		os_type: string | null;
		os_distro: string | null;
		created_at: string | null;
	}

	let { images, selectedId, onSelect }: {
		images: ImageInfo[];
		selectedId: string | null;
		onSelect: (id: string, name: string) => void;
	} = $props();

	let activeDistro = $state<string | null>(null);

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

	const filteredImages = $derived(
		activeDistro === null
			? images
			: images.filter(i => (i.os_distro ?? '기타') === activeDistro)
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
			// Extract version from name (e.g., "ubuntu-24.04-server-..." → "24.04 LTS")
			const m = img.name.match(/(\d{2}\.\d{2})/);
			if (m) parts.push(`${label} ${m[1]} LTS`);
			else parts.push(label);
		}
		if (img.os_type) parts.push(img.os_type);
		return parts.join(' · ') || img.name;
	}
</script>

<div class="flex flex-wrap gap-2 mb-5">
	<button
		onclick={() => activeDistro = null}
		class="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors {activeDistro === null
			? 'bg-blue-600 text-white'
			: 'bg-gray-800 text-gray-400 hover:bg-gray-700'}"
	>전체 ({images.length})</button>
	{#each distros as d}
		{@const count = images.filter(i => (i.os_distro ?? '기타') === d).length}
		<button
			onclick={() => activeDistro = d}
			class="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors {activeDistro === d
				? 'bg-blue-600 text-white'
				: 'bg-gray-800 text-gray-400 hover:bg-gray-700'}"
		>{distroLabel(d)} ({count})</button>
	{/each}
</div>

<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
	{#each filteredImages as img}
		<button
			onclick={() => onSelect(img.id, img.name)}
			class="relative text-left p-4 rounded-xl border transition-all {selectedId === img.id
				? 'border-blue-500 bg-blue-900/20 ring-1 ring-blue-500/30'
				: 'border-gray-700 bg-gray-900 hover:border-gray-500'}"
		>
			<!-- 선택 체크마크 -->
			{#if selectedId === img.id}
				<div class="absolute top-3 right-3 w-5 h-5 bg-blue-500 rounded-full flex items-center justify-center">
					<svg class="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"/>
					</svg>
				</div>
			{/if}

			<!-- 아바타 + 이름 -->
			<div class="flex items-start gap-3 mb-2">
				{#if logoPath(img.os_distro)}
					<img src={logoPath(img.os_distro)} alt={img.os_distro ?? ''} class="w-8 h-8 rounded-lg object-contain bg-gray-800 p-0.5 flex-shrink-0" />
				{:else}
					<div class="w-8 h-8 rounded-lg {avatarColor(img.os_distro)} flex items-center justify-center text-white text-sm font-bold flex-shrink-0">
						{avatarLetter(img.name)}
					</div>
				{/if}
				<div class="min-w-0 flex-1">
					<div class="font-medium text-white text-sm truncate">{img.name}</div>
					<div class="text-xs text-gray-500 truncate">{distroDescription(img)}</div>
				</div>
			</div>

			<!-- 상세 정보 -->
			<div class="flex items-center gap-3 text-xs text-gray-500 mt-2">
				{#if img.disk_format}
					<span class="px-1.5 py-0.5 bg-gray-800 border border-gray-700 rounded text-gray-400">{img.disk_format}</span>
				{/if}
				{#if img.min_disk}
					<span>{img.min_disk} GB</span>
				{/if}
				{#if img.created_at}
					<span>{formatDate(img.created_at)}</span>
				{/if}
			</div>
		</button>
	{/each}
</div>
