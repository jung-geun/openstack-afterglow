<script lang="ts">
	import AutoRefreshControl from '../AutoRefreshControl.svelte';

	interface Props {
		active?: boolean;
		intervalSeconds?: number;
		intervalOptions?: number[];
		refreshing?: boolean;
		onManualRefresh?: () => void;
	}

	let {
		active = $bindable(false),
		intervalSeconds = $bindable(30),
		intervalOptions = [10, 30, 60],
		refreshing = false,
		onManualRefresh = () => {}
	}: Props = $props();
</script>

<div>
	<AutoRefreshControl
		bind:active
		bind:intervalSeconds
		{intervalOptions}
		{refreshing}
		{onManualRefresh}
	/>
	<div data-testid="active-state">{active}</div>
	<div data-testid="interval-state">{intervalSeconds}</div>
</div>
