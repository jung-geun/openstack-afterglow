<script lang="ts">
	import { toast } from '$lib/stores/toast';

	const typeStyles: Record<string, string> = {
		success: 'bg-green-900/90 border-green-700 text-green-100',
		error: 'bg-red-900/90 border-red-700 text-red-100',
		warning: 'bg-yellow-900/90 border-yellow-700 text-yellow-100',
		info: 'bg-blue-900/90 border-blue-700 text-blue-100',
	};

	const typeIcons: Record<string, string> = {
		success: '✓',
		error: '✕',
		warning: '⚠',
		info: 'ℹ',
	};
</script>

{#if $toast.length > 0}
<div class="fixed top-16 right-4 z-[60] flex flex-col gap-2 w-80 pointer-events-none">
	{#each $toast as t (t.id)}
		<div class="flex items-start gap-3 px-4 py-3 rounded-lg border text-sm shadow-xl pointer-events-auto
			{typeStyles[t.type]}">
			<span class="flex-shrink-0 font-bold text-base leading-none mt-0.5">{typeIcons[t.type]}</span>
			<span class="flex-1 break-words">{t.message}</span>
			<button
				onclick={() => toast.remove(t.id)}
				class="flex-shrink-0 opacity-50 hover:opacity-100 transition-opacity text-lg leading-none mt-0.5"
			>×</button>
		</div>
	{/each}
</div>
{/if}
