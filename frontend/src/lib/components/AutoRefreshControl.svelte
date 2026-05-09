<script lang="ts">
	import { onMount } from 'svelte';

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
		onManualRefresh,
	}: Props = $props();

	let isLight = $state(false);
	onMount(() => {
		isLight = document.documentElement.classList.contains('light');
		const obs = new MutationObserver(() => {
			isLight = document.documentElement.classList.contains('light');
		});
		obs.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
		return () => obs.disconnect();
	});

	const selectValue = $derived(active ? String(intervalSeconds) : 'off');

	function handleSelect(e: Event) {
		const v = (e.currentTarget as HTMLSelectElement).value;
		if (v === 'off') {
			active = false;
		} else {
			active = true;
			intervalSeconds = parseInt(v, 10);
		}
	}
</script>

<div
	class="flex items-center rounded border overflow-hidden text-xs"
	style="border-color: {isLight ? '#d1d5db' : '#374151'}"
>
	<button
		type="button"
		onclick={onManualRefresh}
		disabled={refreshing}
		title={refreshing ? '로딩 중…' : '지금 새로고침'}
		class="flex items-center gap-1.5 px-2.5 py-1.5 transition-colors disabled:opacity-50
			{isLight
				? 'bg-white text-gray-700 hover:bg-gray-50'
				: 'bg-gray-800 text-gray-300 hover:bg-gray-700'}"
	>
		<svg
			class="w-3.5 h-3.5 {refreshing ? 'animate-spin' : ''}"
			style={refreshing ? 'animation-direction: reverse' : ''}
			fill="none"
			stroke="currentColor"
			stroke-width="2"
			viewBox="0 0 24 24"
		>
			<path
				stroke-linecap="round"
				stroke-linejoin="round"
				d="M4 4v5h5M20 20v-5h-5M4 9a8 8 0 0114.93-3M20 15a8 8 0 01-14.93 3"
			/>
		</svg>
		<span class="hidden md:inline">새로고침</span>
	</button>
	<select
		value={selectValue}
		onchange={handleSelect}
		title="새로고침 주기"
		class="py-1.5 pl-2 pr-1 border-l cursor-pointer focus:outline-none transition-colors
			{isLight
				? 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
				: 'bg-gray-800 text-gray-400 border-gray-700 hover:bg-gray-700'}"
	>
		<option value="off">Off</option>
		{#each intervalOptions as opt}
			<option value={String(opt)}>{opt}s</option>
		{/each}
	</select>
</div>
