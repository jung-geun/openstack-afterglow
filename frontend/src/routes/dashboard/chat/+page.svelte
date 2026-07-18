<script lang="ts">
	import { SectionHeader } from '$lib/components/ui';
	import ChatPanel from '$lib/components/chat/ChatPanel.svelte';
</script>

<div class="space-y-4">
	<SectionHeader title="AI 채팅" meta="빌트인 LLM 채팅 (litellm 라우팅)" />
	<ChatPanel />
</div>
