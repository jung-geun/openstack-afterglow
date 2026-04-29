<script lang="ts">
	interface Props {
		active: boolean;
		intervalSeconds: number;
		intervalOptions?: number[];
		refreshing?: boolean;
		onManualRefresh: () => void;
	}

	let {
		active = $bindable(),
		intervalSeconds = $bindable(),
		intervalOptions = [10, 15, 30, 60],
		refreshing = false,
		onManualRefresh
	}: Props = $props();
</script>

<div class="flex items-center gap-1.5">
	<div class="flex items-center gap-0 rounded border border-gray-700 overflow-hidden text-xs">
		<button
			onclick={() => (active = !active)}
			class="px-2 py-1.5 transition-colors {active
				? 'bg-blue-600/20 text-blue-400 hover:bg-blue-600/30'
				: 'bg-gray-800 text-gray-500 hover:text-gray-300 hover:bg-gray-700'}"
			title={active ? '자동 새로고침 끄기' : '자동 새로고침 켜기'}
		>
			{#if active}
				<span class="inline-flex items-center gap-1">
					<svg class="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
						<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
						<path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4l3-3-3-3v4a10 10 0 100 20v-2a8 8 0 01-8-8z"></path>
					</svg>
					자동
				</span>
			{:else}
				<span class="inline-flex items-center gap-1">
					<svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
						<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clip-rule="evenodd"/>
					</svg>
					자동
				</span>
			{/if}
		</button>
		<select
			bind:value={intervalSeconds}
			class="bg-gray-800 text-gray-400 py-1.5 px-1 border-l border-gray-700 focus:outline-none text-xs cursor-pointer hover:bg-gray-700 transition-colors"
			title="새로고침 주기"
		>
			{#each intervalOptions as opt}
				<option value={opt}>{opt}s</option>
			{/each}
		</select>
	</div>
	<button
		onclick={onManualRefresh}
		disabled={refreshing}
		class="text-xs text-gray-400 hover:text-white transition-colors px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600 disabled:opacity-50"
	>
		{refreshing ? '로딩 중…' : '새로고침'}
	</button>
</div>
