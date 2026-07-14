<script lang="ts">
	import { SectionHeader } from '$lib/components/ui';
	import LibreChatEmbed from '$lib/components/LibreChatEmbed.svelte';
</script>

<div class="space-y-4">
	<SectionHeader title="AI 채팅" meta="LibreChat 기반 LLM 채팅 서비스" />
	<LibreChatEmbed />
</div>
