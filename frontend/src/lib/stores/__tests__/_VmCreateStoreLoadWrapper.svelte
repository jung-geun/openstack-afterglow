<script lang="ts">
	import { createVmCreateStore } from '../vmCreateStore.svelte';

	const store = createVmCreateStore({ adminMode: () => false });
</script>

<button data-testid="init" onclick={() => store.init()}>init</button>
<button data-testid="step-five" onclick={() => store.goTo(5)}>step five</button>
<span data-testid="loading">{store.loading ? 'loading' : 'ready'}</span>
