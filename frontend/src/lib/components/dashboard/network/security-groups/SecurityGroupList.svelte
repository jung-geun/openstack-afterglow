<script lang="ts">
	import type { SecurityGroup } from '$lib/types/resources';

	let {
		groups,
		selectedSg = $bindable(),
	}: {
		groups: SecurityGroup[];
		selectedSg: string | null;
	} = $props();
</script>

<div class="flex flex-col gap-2">
	{#each groups as sg (sg.id)}
		<div
			onclick={() => selectedSg = sg.name}
			onkeydown={(e) => e.key === 'Enter' && (selectedSg = sg.name)}
			tabindex="0"
			role="button"
			class="p-3.5 rounded-[10px] border cursor-pointer transition-colors
				{selectedSg === sg.name ? 'bg-blue-600/10 border-blue-800' : 'bg-[#0B1220] border-gray-800 hover:border-gray-700'}"
		>
			<div class="flex items-center gap-2">
				<!-- Shield icon -->
				<div class="shrink-0 w-6 h-6 rounded-md {selectedSg === sg.name ? 'bg-blue-500/20 border border-blue-500/40' : 'bg-gray-800 border border-gray-700'} flex items-center justify-center">
					<svg class="w-3 h-3 {selectedSg === sg.name ? 'text-blue-400' : 'text-gray-400'}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
					</svg>
				</div>
				<div class="text-white font-medium text-[13px] font-mono truncate">{sg.name}</div>
				<span class="ml-auto text-[11px] text-gray-500 shrink-0">{sg.rules?.length ?? 0}</span>
			</div>
			{#if sg.description}
				<div class="text-[11px] text-gray-400 mt-1.5 leading-snug truncate">{sg.description}</div>
			{/if}
		</div>
	{/each}
</div>
