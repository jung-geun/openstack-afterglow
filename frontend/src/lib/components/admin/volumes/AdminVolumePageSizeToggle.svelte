<script lang="ts">
	let {
		value,
		options = [10, 20, 30],
		onChange,
	}: {
		value: number;
		options?: number[];
		onChange: (n: number) => void;
	} = $props();
</script>

<div class="flex items-center gap-1 text-xs text-gray-500 max-md:hidden">
	표시:
	{#each options as n}
		<button
			onclick={() => onChange(n)}
			class="px-2 py-0.5 rounded {value === n ? 'bg-blue-600 text-white' : 'bg-gray-800 hover:bg-gray-700 text-gray-400'}"
		>{n}</button>
	{/each}
</div>
