<script lang="ts">
	import ChatPanel from '$lib/components/chat/ChatPanel.svelte';

	let {
		data
	}: {
		data: { workspaceId: number | null; initialSettingsSection: 'usage' | 'mcp' };
	} = $props();
</script>

<ChatPanel initialWorkspaceId={data.workspaceId} initialSettingsSection={data.initialSettingsSection} />
