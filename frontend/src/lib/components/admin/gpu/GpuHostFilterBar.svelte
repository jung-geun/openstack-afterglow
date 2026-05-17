<script lang="ts">
	let {
		availableFilter = $bindable(),
		selectedGpuTypes = $bindable(),
	}: {
		availableFilter: 'all' | 'available' | 'full';
		selectedGpuTypes: Set<string>;
	} = $props();
</script>

<div class="flex items-center gap-2 mb-3 flex-wrap">
	<span class="text-xs text-gray-500">필터:</span>
	<button
		onclick={() => (availableFilter = 'all')}
		class="text-xs px-2.5 py-1 rounded transition-colors {availableFilter === 'all' ? 'bg-gray-700 text-white' : 'text-gray-400 hover:text-white'}"
	>전체</button>
	<button
		onclick={() => (availableFilter = 'available')}
		class="text-xs px-2.5 py-1 rounded transition-colors {availableFilter === 'available' ? 'bg-green-900/50 text-green-400' : 'text-gray-400 hover:text-white'}"
	>사용 가능</button>
	<button
		onclick={() => (availableFilter = 'full')}
		class="text-xs px-2.5 py-1 rounded transition-colors {availableFilter === 'full' ? 'bg-red-900/50 text-red-400' : 'text-gray-400 hover:text-white'}"
	>모두 사용 중</button>
	{#if selectedGpuTypes.size > 0}
		<span class="text-gray-600 text-xs">|</span>
		<span class="text-xs text-blue-400">GPU 필터: {Array.from(selectedGpuTypes).join(', ')}</span>
		<button onclick={() => (selectedGpuTypes = new Set())} class="text-xs text-gray-500 hover:text-white transition-colors">✕ 초기화</button>
	{/if}
</div>
