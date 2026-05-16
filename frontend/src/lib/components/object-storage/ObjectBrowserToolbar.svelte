<script lang="ts">
	import { useObjectBrowser } from '$lib/stores/objectBrowser.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';

	interface ArState { active: boolean; intervalSeconds: number; intervalOptions: number[]; }
	interface Props { ar: ArState; onManualRefresh: () => void; }
	let { ar, onManualRefresh }: Props = $props();

	const s = useObjectBrowser();
</script>

<div class="flex items-center gap-2 mb-4 flex-wrap">
	<div class="relative flex-1 min-w-[200px] max-w-xs">
		<svg class="w-4 h-4 text-gray-500 absolute left-3 top-1/2 -translate-y-1/2" viewBox="0 0 20 20" fill="currentColor">
			<path fill-rule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clip-rule="evenodd"/>
		</svg>
		<input
			type="text"
			bind:value={s.filterText}
			placeholder="파일 필터..."
			class="w-full bg-gray-800 border border-gray-700 rounded-lg pl-9 pr-3 py-1.5 text-sm text-white focus:outline-none focus:border-indigo-500 placeholder-gray-600"
		/>
	</div>

	{#if s.mode === 'user' && s.filterText.trim()}
		<select
			bind:value={s.searchScope}
			title="검색 범위"
			class="text-xs text-gray-300 bg-gray-800 border border-gray-700 rounded-lg px-2 py-1.5 focus:outline-none focus:border-indigo-500"
		>
			<option value="current">현재 폴더</option>
			<option value="expanded">펼친 트리</option>
			<option value="all">전체 버킷</option>
		</select>
		{#if s.searchScope === 'all' && s.allObjectsLoading}
			<span class="text-xs text-gray-500">전체 인덱싱 중...</span>
		{/if}
	{/if}

	<button
		onclick={() => s.toggleSort('name')}
		class="text-xs text-gray-400 hover:text-white px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600 transition-colors"
	>이름순 {s.sortIcon('name')}</button>

	<div class="flex-1"></div>

	{#if s.prefix}
		<button
			onclick={() => {
				const parts = s.prefix.replace(/\/$/, '').split('/');
				parts.pop();
				s.navigatePrefix(parts.length ? parts.join('/') + '/' : '');
			}}
			class="text-xs text-gray-400 hover:text-white transition-colors px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600"
		>← 상위</button>
	{/if}

	<button
		onclick={() => { s.showNewDir = true; s.newDirName = ''; }}
		class="text-xs text-gray-300 hover:text-white bg-gray-800 hover:bg-gray-700 transition-colors px-3 py-1.5 rounded border border-gray-700"
	>새 폴더</button>

	<button
		onclick={() => { s.showUpload = true; }}
		class="text-xs text-white bg-indigo-600 hover:bg-indigo-500 transition-colors px-3 py-1.5 rounded border border-indigo-500"
	>+ 업로드</button>

	<AutoRefreshControl
		bind:active={ar.active}
		bind:intervalSeconds={ar.intervalSeconds}
		intervalOptions={ar.intervalOptions}
		refreshing={s.loading}
		{onManualRefresh}
	/>
</div>
