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
	}

	let { images, selectedId, onSelect }: {
		images: ImageInfo[];
		selectedId: string | null;
		onSelect: (id: string, name: string) => void;
	} = $props();

	let activeDistro = $state<string | null>(null);

	const distroLabels: Record<string, string> = {
		ubuntu: 'Ubuntu', centos: 'CentOS', rocky: 'Rocky Linux',
		debian: 'Debian', fedora: 'Fedora', rhel: 'RHEL',
		windows: 'Windows', cirros: 'CirrOS',
	};

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
</script>

<!-- OS 필터 탭 -->
<div class="flex flex-wrap gap-2 mb-4">
	<button
		onclick={() => activeDistro = null}
		class="px-3 py-1 rounded-lg text-xs font-medium transition-colors {activeDistro === null
			? 'bg-blue-600 text-white'
			: 'bg-gray-800 text-gray-400 hover:bg-gray-700'}"
	>전체 ({images.length})</button>
	{#each distros as d}
		{@const count = images.filter(i => (i.os_distro ?? '기타') === d).length}
		<button
			onclick={() => activeDistro = d}
			class="px-3 py-1 rounded-lg text-xs font-medium transition-colors {activeDistro === d
				? 'bg-blue-600 text-white'
				: 'bg-gray-800 text-gray-400 hover:bg-gray-700'}"
		>{distroLabel(d)} ({count})</button>
	{/each}
</div>

<div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
	{#each filteredImages as img}
		<button
			onclick={() => onSelect(img.id, img.name)}
			class="text-left p-4 rounded-xl border transition-all {selectedId === img.id
				? 'border-blue-500 bg-blue-900/20'
				: 'border-gray-700 bg-gray-900 hover:border-gray-500'}"
		>
			<div class="font-medium text-white text-sm mb-1">{img.name}</div>
			<div class="text-xs text-gray-500 space-y-0.5">
				{#if img.min_disk}
					<div>최소 디스크: {img.min_disk} GB</div>
				{/if}
				{#if img.disk_format}
					<div>형식: {img.disk_format}</div>
				{/if}
			</div>
		</button>
	{/each}
</div>
