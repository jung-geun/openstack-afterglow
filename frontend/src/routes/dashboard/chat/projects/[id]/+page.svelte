<script lang="ts">
	import ChatPanel from '$lib/components/chat/ChatPanel.svelte';

	let { data }: { data: { workspaceId: number } } = $props();
</script>

<ChatPanel projectRoute={data.workspaceId} />
