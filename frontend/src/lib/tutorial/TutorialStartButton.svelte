<script lang="ts">
	import Button from '$lib/components/ui/Button.svelte';
	import { startTour } from './engine';
	import type { TourId } from './tours';

	let { tour }: { tour: TourId } = $props();
</script>

<Button variant="outline" size="sm" onclick={() => void startTour(tour)} ariaLabel="튜토리얼 시작">
	<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
	튜토리얼
</Button>
