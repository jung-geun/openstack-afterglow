<script lang="ts">
	let {
		markerStack,
		nextMarker,
		onPrev,
		onNext,
	}: {
		markerStack: string[];
		nextMarker: string | null;
		onPrev: () => void;
		onNext: () => void;
	} = $props();
</script>

<div class="flex items-center justify-between mt-3">
	<button
		disabled={markerStack.length === 0}
		onclick={onPrev}
		class="px-3 py-1.5 text-xs rounded bg-gray-800 hover:bg-gray-700 text-gray-300 disabled:opacity-30 disabled:cursor-not-allowed"
	>← 이전</button>
	<button
		disabled={!nextMarker}
		onclick={onNext}
		class="px-3 py-1.5 text-xs rounded bg-gray-800 hover:bg-gray-700 text-gray-300 disabled:opacity-30 disabled:cursor-not-allowed"
	>다음 →</button>
</div>
