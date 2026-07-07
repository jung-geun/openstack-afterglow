<script lang="ts">
	import UsageBar from './UsageBar.svelte';

	interface Props {
		label: string;
		used: number;
		limit: number;
		color?: string;
		size?: 'xs' | 'sm' | 'md';
		showValue?: boolean;
		class?: string;
	}

	let { label, used, limit, color: _color, size = 'xs', showValue = true, class: className = '' }: Props = $props();
</script>

<UsageBar {label} value={used} max={limit} {size} {showValue} class={className} />
