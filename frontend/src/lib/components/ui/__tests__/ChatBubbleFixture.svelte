<script lang="ts">
	import ChatBubble from '../ChatBubble.svelte';
</script>

<ChatBubble
	align="start"
	label="Afterglow"
	ariaLabel="Afterglow 응답"
	metadata="Afterglow Chat"
	timestamp="2026-07-26T08:43:00Z"
	timestampLabel="17:43"
	footerVisible={true}
>
	응답 본문
	{#snippet footer()}
		<button type="button">복사</button>
	{/snippet}
</ChatBubble>

<ChatBubble align="end" label="나" ariaLabel="내 메시지">
	첫 줄
	둘째 줄: verylongunbrokenmessagetokenwithoutspacesmustremaincontainedinthebubble
</ChatBubble>
