<script lang="ts">
	import type { ImageInfo } from '$lib/types/compute';
	import { imageReferenceMatchesQuery, parseImageReference } from '$lib/utils/imageReference';
	import type { ImageReferenceParts } from '$lib/utils/imageReference';
	let { images, selectedId, onSelect }: {
		images: ImageInfo[];
		selectedId: string | null;
		onSelect: (id: string, name: string) => void;
	} = $props();

	let activeDistro = $state<string | null>(null);

	function referenceParts(image: ImageInfo): ImageReferenceParts {
		if (image.repository) {
			const tag = image.tag ?? 'latest';
			return { repository: image.repository, tag, name: `${image.repository}:${tag}` };
		}
		try {
			return parseImageReference(image.name);
		} catch {
			const tag = image.tag ?? 'latest';
			return { repository: image.name, tag, name: `${image.name}:${tag}` };
		}
	}

	function selectionName(image: ImageInfo, reference: ImageReferenceParts): string {
		const sourceName = image.name.trim();
		return sourceName && sourceName !== reference.repository ? sourceName : reference.name;
	}
	let searchTerm = $state('');

	const distroLabels: Record<string, string> = {
		ubuntu: 'Ubuntu', centos: 'CentOS', rocky: 'Rocky Linux',
		debian: 'Debian', 'fedora-coreos': 'Fedora CoreOS', fedora: 'Fedora', rhel: 'RHEL',
		windows: 'Windows', cirros: 'CirrOS',
	};

	const distroColors: Record<string, string> = {
		ubuntu: 'bg-[var(--color-warm)]', centos: 'bg-[var(--color-accent-2)]', rocky: 'bg-[var(--color-state-success)]',
		debian: 'bg-[var(--color-chart-3)]', fedora: 'bg-[var(--color-accent)]', 'fedora-coreos': 'bg-[var(--color-chart-6)]',
		rhel: 'bg-[var(--color-warm-2)]', windows: 'bg-[var(--color-state-info)]', cirros: 'bg-[var(--color-state-neutral)]',
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
		distroFiltered.filter((image) => imageReferenceMatchesQuery(image, searchTerm))
	);

	function distroLabel(d: string): string {
		return distroLabels[d] ?? d;
	}

	function avatarLetter(name: string): string {
		return name.charAt(0).toUpperCase();
	}

	function avatarColor(distro: string | null): string {
		return distroColors[distro ?? ''] ?? 'bg-[var(--color-state-neutral)]';
	}

	function formatDate(dateStr: string | null): string {
		if (!dateStr) return '';
		return dateStr.slice(0, 10);
	}

	function distroDescription(img: ImageInfo): string {
		const parts: string[] = [];
		const reference = referenceParts(img);
		const label = distroLabels[img.os_distro ?? ''] ?? '';
		if (label) {
			const m = `${img.name} ${reference.repository} ${reference.tag}`.match(/(\d{2}\.\d{2})/);
			if (m) parts.push(`${label} ${m[1]} LTS`);
			else parts.push(label);
		}
		if (img.os_type) parts.push(img.os_type);
		return parts.join(' · ') || reference.name;
	}
</script>

<!-- 검색바 -->
<div class="relative mb-4">
	<span class="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-ink-3)] pointer-events-none">
		<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
			<circle cx="11" cy="11" r="7"/>
			<path stroke-linecap="round" stroke-linejoin="round" d="m21 21-4.3-4.3"/>
		</svg>
	</span>
	<label for="vm-image-search" class="sr-only">이미지 이름, tag, OS 검색</label>
	<input
		id="vm-image-search"
		type="search"
		bind:value={searchTerm}
		placeholder="이미지명, repository, tag, OS, 버전으로 검색…"
		class="w-full bg-[var(--color-surface-raised)] border border-[var(--color-line)] text-[var(--color-ink-1)] rounded-lg pl-9 pr-3 py-2 text-sm outline-none focus:border-[var(--color-line-2)] placeholder:text-[var(--color-ink-3)]"
	/>
</div>

<!-- OS family 칩 -->
<div class="flex flex-wrap gap-2 mb-5">
	<button
		onclick={() => activeDistro = null}
		class="inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-medium transition-all {activeDistro === null
			? 'bg-[var(--color-accent)] text-[var(--color-action-on-accent)]'
			: 'bg-[var(--color-surface-sunken)] text-[var(--color-ink-2)] hover:bg-[var(--color-surface-raised)]'}"
	>전체 <span class="opacity-70 font-mono text-[10.5px]">{images.length}</span></button>
	{#each distros as d}
		{@const count = images.filter(i => (i.os_distro ?? '기타') === d).length}
		<button
			onclick={() => activeDistro = d}
			class="inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-medium transition-all {activeDistro === d
				? 'bg-[var(--color-accent)] text-[var(--color-action-on-accent)]'
				: 'bg-[var(--color-surface-sunken)] text-[var(--color-ink-2)] hover:bg-[var(--color-surface-raised)]'}"
		>{distroLabel(d)} <span class="opacity-70 font-mono text-[10.5px]">{count}</span></button>
	{/each}
</div>

<!-- 이미지 카드 그리드 -->
<div class="grid grid-cols-1 @lg/panel:grid-cols-2 @3xl/panel:grid-cols-3 gap-3">
	{#each filteredImages as img}
		{@const reference = referenceParts(img)}
		<button
			onclick={() => onSelect(img.id, selectionName(img, reference))}
			aria-label={`${reference.name} 이미지 선택`}
			class="relative text-left p-4 rounded-xl border transition-all hover:-translate-y-px hover:shadow-md {selectedId === img.id
				? 'border-[var(--color-accent)] bg-[var(--color-accent)]/10 ring-1 ring-[var(--color-accent)]/30'
				: 'border-[var(--color-line)] bg-[var(--color-surface-raised)] hover:border-[var(--color-line-2)]'}"
		>
			<!-- 선택 체크마크 (우측 상단 pill) -->
			{#if selectedId === img.id}
				<div class="absolute top-3.5 right-3.5 w-5 h-5 bg-[var(--color-accent)] rounded-full flex items-center justify-center">
					<svg class="w-3 h-3 text-[var(--color-action-on-accent)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
						class="w-9 h-9 rounded-lg object-contain bg-[var(--color-surface-sunken)] border border-[var(--color-line)] p-0.5 flex-shrink-0"
					/>
				{:else}
					<div class="w-9 h-9 rounded-lg {avatarColor(img.os_distro ?? null)} flex items-center justify-center text-[var(--color-action-on-accent)] text-sm font-bold flex-shrink-0 border border-[var(--color-ink-0)]/10">
						{avatarLetter(img.name)}
					</div>
				{/if}
				<div class="min-w-0 flex-1">
					<div class="font-semibold text-[var(--color-ink-0)] text-[13.5px] font-mono truncate leading-tight">{reference.repository}</div>
					<div class="text-[11px] text-[var(--color-ink-3)] truncate mt-0.5">{distroDescription(img)}</div>
				</div>
			</div>

			<!-- 메타 -->
			<div class="flex items-center gap-2 text-[11px] text-[var(--color-ink-3)] font-mono pt-2 mt-2 border-t border-[var(--color-line)]">
				<span class="px-1.5 py-0.5 bg-[var(--color-surface-sunken)] border border-[var(--color-line)] rounded text-[var(--color-ink-2)] text-[10px]">tag:{reference.tag}</span>
				{#if img.disk_format}
					<span class="px-1.5 py-0.5 bg-[var(--color-surface-sunken)] border border-[var(--color-line)] rounded text-[var(--color-ink-2)] text-[10px] lowercase">{img.disk_format}</span>
				{/if}
				{#if img.min_disk}
					<span>{img.min_disk} GB</span>
				{/if}
				{#if img.updated_at ?? img.created_at}
					<span class="ml-auto">{formatDate(img.updated_at ?? img.created_at ?? null)}</span>
				{/if}
			</div>
		</button>
	{/each}

	{#if filteredImages.length === 0}
		<div class="col-span-3 text-center py-10 text-[var(--color-ink-3)] text-sm">
			조건에 맞는 이미지가 없습니다
		</div>
	{/if}
</div>
