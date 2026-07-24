<script lang="ts">
	let {
		onIntentInstance,
		onIntentRouter,
		onCancelIntent,
	}: {
		onIntentInstance: (id: string) => void;
		onIntentRouter: (id: string) => void;
		onCancelIntent: () => void;
	} = $props();
</script>

<button
	type="button"
	onpointerenter={() => onIntentInstance('instance-1')}
	onpointerleave={onCancelIntent}
	onfocus={() => onIntentInstance('instance-1')}
	onblur={onCancelIntent}
>instance intent</button>
<button
	type="button"
	onpointerenter={() => onIntentRouter('router-1')}
	onpointerleave={onCancelIntent}
	onfocus={() => onIntentRouter('router-1')}
	onblur={onCancelIntent}
>router intent</button>
