<script lang="ts">
	let {
		images = [],
		onintent,
		onNext,
	}: {
		images?: Array<{ id: string; name: string }>;
		onintent?: () => void;
		onNext: () => void;
	} = $props();
</script>

{#each images as image}
	<span>{image.name}</span>
{/each}

<button type="button" onpointerenter={() => onintent?.()} onfocus={() => onintent?.()} onclick={onNext}>다음 이미지</button>
