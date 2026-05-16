<script lang="ts">
	import { useObjectBrowser } from '$lib/stores/objectBrowser.svelte';

	const s = useObjectBrowser();

	const backHref = $derived(
		s.mode === 'user'
			? '/dashboard/object-storage/buckets'
			: '/admin/object-storage'
	);
</script>

<div class="flex items-center gap-1 mb-2 flex-wrap text-sm">
	<a href={backHref} class="text-gray-500 hover:text-gray-300 flex items-center gap-1">
		<svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
			<path fill-rule="evenodd" d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z" clip-rule="evenodd"/>
		</svg>
		버킷 목록
	</a>
</div>

<div class="text-[10px] text-gray-600 uppercase tracking-widest mb-3">OBJECT STORAGE / EXPLORER</div>

<div class="flex items-start justify-between mb-4">
	<div>
		<h1 class="text-2xl font-bold text-white">{s.containerName}</h1>
		{#if s.containerMeta}<p class="text-gray-500 text-xs mt-1">데이터 동기화 완료</p>{/if}
	</div>
	{#if s.containerMeta}
		<div class="flex gap-4 text-center">
			<div class="bg-gray-900 border border-gray-800 rounded-lg px-4 py-2">
				<div class="text-[10px] text-gray-500 uppercase tracking-wider">총 용량</div>
				<div class="text-lg font-bold text-white">
					{s.containerMeta.bytes >= 1073741824
						? (s.containerMeta.bytes / 1073741824).toFixed(2)
						: s.containerMeta.bytes >= 1048576
						? (s.containerMeta.bytes / 1048576).toFixed(1)
						: Math.round(s.containerMeta.bytes / 1024).toString()}
					<span class="text-xs text-gray-500 font-normal">
						{s.containerMeta.bytes >= 1073741824 ? 'GB' : s.containerMeta.bytes >= 1048576 ? 'MB' : 'KB'}
					</span>
				</div>
			</div>
			<div class="bg-gray-900 border border-gray-800 rounded-lg px-4 py-2">
				<div class="text-[10px] text-gray-500 uppercase tracking-wider">객체 수</div>
				<div class="text-lg font-bold text-white">{s.containerMeta.count} <span class="text-xs text-gray-500 font-normal">Items</span></div>
			</div>
		</div>
	{/if}
</div>

<div class="flex items-center gap-1 mb-4 text-sm">
	<button onclick={() => s.navigatePrefix('')} class="text-indigo-400 hover:text-indigo-300 font-medium">{s.containerName}</button>
	{#each s.breadcrumbs as seg, i}
		<svg class="w-3 h-3 text-gray-600 shrink-0" viewBox="0 0 20 20" fill="currentColor">
			<path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd"/>
		</svg>
		<button onclick={() => s.navigatePrefix(s.breadcrumbPrefix(i))} class="text-indigo-400 hover:text-indigo-300 font-medium">{seg}</button>
	{/each}
</div>
