<script lang="ts">
	import { SectionHeader } from '$lib/components/ui';
	import ChatExtensionsManager from '$lib/components/chat/ChatExtensionsManager.svelte';
</script>

<div class="space-y-4 p-4 md:p-8 max-w-4xl">
	<div class="flex items-center justify-between gap-3">
		<SectionHeader title="내 AI 도구" meta="채팅에서 사용할 MCP 서버와 커스텀 툴을 직접 추가합니다" />
		<a href="/dashboard/chat" class="shrink-0 text-sm text-[var(--color-ink-3)] transition-colors hover:text-[var(--color-ink-1)]">← 채팅으로</a>
	</div>
	<ChatExtensionsManager base="/api/v1/chat" />
</div>
