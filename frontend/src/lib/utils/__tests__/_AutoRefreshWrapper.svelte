<script lang="ts">
	import { createAutoRefresh } from '../autoRefresh.svelte';

	interface Props {
		fn?: () => void;
		storageKey?: string;
		defaultActive?: boolean;
		defaultInterval?: number;
		invokeOnMount?: boolean;
	}

	let {
		fn = () => {},
		storageKey = 'test-key',
		defaultActive = true,
		defaultInterval = 30,
		invokeOnMount = false,
	}: Props = $props();

	let state = createAutoRefresh(fn, {
		storageKey,
		defaultActive,
		defaultInterval,
		invokeOnMount,
	});
</script>

<div data-testid="active">{state.active}</div>
<div data-testid="interval">{state.intervalSeconds}</div>
