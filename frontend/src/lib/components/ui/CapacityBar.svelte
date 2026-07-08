<script lang="ts">
	import UsageBar from './UsageBar.svelte';

	interface Props {
		label: string;
		used: number;
		total: number;
		unit?: string;
		size?: 'xs' | 'sm' | 'md';
		class?: string;
	}

	let { label, used, total, unit = '', size = 'sm', class: className = '' }: Props = $props();
</script>

<UsageBar {label} value={used} max={total} {unit} {size} class={className} />
