<script lang="ts">
	import StorageAttachmentsSection from '../StorageAttachmentsSection.svelte';
	import { provideInstanceDetailController, type InstanceDetailController } from '$lib/stores/instanceDetailController.svelte';

	let instanceId = $state<string | null>('instance-a');
	let projectId = $state<string | null>('project-a');
	const controller = {
		get instanceId() { return instanceId ?? undefined; },
		get effectiveProjectId() { return projectId ?? undefined; },
	} as InstanceDetailController;
	provideInstanceDetailController(controller);
</script>

<button data-testid="clear-instance" onclick={() => instanceId = null}>clear instance</button>
<button data-testid="set-instance-a" onclick={() => instanceId = 'instance-a'}>set instance a</button>
<button data-testid="set-instance-b" onclick={() => instanceId = 'instance-b'}>set instance b</button>
<button data-testid="clear-project" onclick={() => projectId = null}>clear project</button>
<StorageAttachmentsSection />
