<script lang="ts">
	import { wizard } from '../wizard';
	import { createVmCreateStore } from '../vmCreateStore.svelte';

	const store = createVmCreateStore({ adminMode: () => false });
</script>

<button data-testid="select-image" onclick={() => store.selectImage('image-1', 'Ubuntu 24.04')}>이미지 선택</button>
<button data-testid="select-flavor" onclick={() => store.selectFlavor('flavor-1', 'm1.small')}>플레이버 선택</button>
<button data-testid="previous-step" onclick={store.prevStep}>이전</button>
<span data-testid="wizard-step">{$wizard.step}</span>
