<script lang="ts">
	import { untrack } from 'svelte';
	import ChatMessage from './ChatMessage.svelte';
	import {
		getSiblingInfo,
		type AvailableModel,
		type ChatMessage as ChatMsg
	} from '$lib/api/chatTree';

	type DisplayMessage = ChatMsg & { streaming?: boolean };
	interface Props {
		activePath: DisplayMessage[];
		allMessages: ChatMsg[];
		models: AvailableModel[];
		busy?: boolean;
		loading?: boolean;
		modelLocked?: boolean;
		toolActivity?: string | null;
		error?: string | null;
		empty?: boolean;
		tempMode?: boolean;
		onCopy: (text: string) => void;
		onRegenerate: (messageId: string, modelName: string) => void;
		onFork: (messageId: string) => void;
		onSwitchVersion: (messageId: string, direction: -1 | 1) => void;
	}
	let {
		activePath,
		allMessages,
		models,
		busy = false,
		loading = false,
		modelLocked = false,
		toolActivity = null,
		error = null,
		empty = false,
		tempMode = false,
		onCopy,
		onRegenerate,
		onFork,
		onSwitchVersion
	}: Props = $props();

	let scrollEl = $state<HTMLDivElement | null>(null);

	function modelDisplay(name: string | null | undefined): string | null {
		if (!name) return null;
		return models.find((m) => m.model_name === name)?.display_name ?? name;
	}

	function siblingInfo(msg: DisplayMessage) {
		// 스트리밍 중인 낙관적 메시지(id 없음)는 형제 계산 제외
		if (msg.streaming || !allMessages.some((m) => m.id === msg.id)) {
			return { index: 1, total: 1 };
		}
		const info = getSiblingInfo(allMessages, msg);
		return { index: info.index, total: info.total };
	}

	// 새 메시지/델타 도착 시 하단으로 스크롤
	$effect(() => {
		void activePath.length;
		const last = activePath[activePath.length - 1];
		if (last) void last.content;
		const el = scrollEl;
		if (el) untrack(() => (el.scrollTop = el.scrollHeight));
	});
</script>

<div class="window">
	{#if loading}
		<div class="load-bar" role="status" aria-label="불러오는 중"><span></span></div>
	{/if}
	{#if tempMode}
		<div class="temp-banner">
			<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 8v4l2.5 2.5M12 3a9 9 0 1 0 9 9" stroke-linecap="round" stroke-linejoin="round" /></svg>
			<span>임시 채팅 — 이 대화는 저장되지 않습니다.</span>
		</div>
	{/if}

	<div class="scroll" bind:this={scrollEl}>
		{#if empty}
			<div class="welcome">
				<div class="welcome-mark">
					<svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M21 11.5a8.38 8.38 0 0 1-8.5 8.5 8.5 8.5 0 0 1-3.8-.9L3 21l1.9-5.7A8.5 8.5 0 0 1 12.5 3 8.38 8.38 0 0 1 21 11.5z" stroke-linecap="round" stroke-linejoin="round" /></svg>
				</div>
				<h2>무엇을 도와드릴까요?</h2>
				<p>아래에 메시지를 입력해 대화를 시작하세요.</p>
			</div>
		{:else}
			<div class="stream">
				{#each activePath as msg (msg.id)}
					{@const info = siblingInfo(msg)}
					<ChatMessage
						message={msg}
						{models}
						{busy}
						{modelLocked}
						siblingIndex={info.index}
						siblingTotal={info.total}
						modelDisplayName={modelDisplay(msg.model_name)}
						{onCopy}
						onRegenerate={(model) => onRegenerate(msg.id, model)}
						onFork={() => onFork(msg.id)}
						onPrevVersion={() => onSwitchVersion(msg.id, -1)}
						onNextVersion={() => onSwitchVersion(msg.id, 1)}
					/>
				{/each}

				{#if toolActivity}
					<div class="tool-activity">
						<span class="spinner"></span>
						도구 실행 중: {toolActivity}…
					</div>
				{/if}
			</div>
		{/if}
	</div>

	{#if error}
		<div class="error-bar" role="alert">{error}</div>
	{/if}
</div>

<style>
	.window {
		display: flex;
		flex-direction: column;
		flex: 1;
		min-height: 0;
		min-width: 0;
		position: relative;
	}
	.load-bar {
		position: absolute;
		top: 0;
		left: 0;
		right: 0;
		height: 2px;
		overflow: hidden;
		background: color-mix(in oklab, var(--color-accent) 20%, transparent);
		z-index: 5;
	}
	.load-bar span {
		display: block;
		width: 40%;
		height: 100%;
		background: var(--color-accent);
		animation: indeterminate 1.1s ease-in-out infinite;
	}
	@keyframes indeterminate {
		0% { transform: translateX(-100%); }
		100% { transform: translateX(300%); }
	}
	.temp-banner {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.4rem;
		padding: 0.5rem;
		font-size: 0.75rem;
		color: var(--color-ink-2);
		background: var(--color-surface-sunken);
		border-bottom: 1px solid var(--color-line);
	}
	.scroll {
		flex: 1;
		min-height: 0;
		overflow-y: auto;
		padding: 1.5rem 1rem;
	}
	.stream {
		display: flex;
		flex-direction: column;
		gap: 1.25rem;
		max-width: 52rem;
		margin: 0 auto;
	}
	.welcome {
		height: 100%;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		text-align: center;
		gap: 0.4rem;
	}
	.welcome-mark {
		width: 3.5rem;
		height: 3.5rem;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 1rem;
		margin-bottom: 0.6rem;
		color: var(--color-accent);
		background: var(--color-surface-sunken);
		border: 1px solid var(--color-line);
	}
	.welcome h2 {
		margin: 0;
		font-size: 1.15rem;
		font-weight: 650;
		color: var(--color-ink-0);
	}
	.welcome p {
		margin: 0;
		font-size: 0.85rem;
		color: var(--color-ink-3);
	}
	.tool-activity {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.78rem;
		color: var(--color-ink-2);
	}
	.spinner {
		width: 0.8rem;
		height: 0.8rem;
		border-radius: 50%;
		border: 2px solid var(--color-line-2);
		border-top-color: var(--color-accent);
		animation: spin 0.8s linear infinite;
	}
	@keyframes spin {
		to { transform: rotate(360deg); }
	}
	.error-bar {
		margin: 0 1rem 0.75rem;
		padding: 0.55rem 0.8rem;
		border-radius: 0.5rem;
		font-size: 0.8rem;
		color: var(--color-state-danger);
		background: color-mix(in oklab, var(--color-state-danger) 12%, transparent);
		border: 1px solid color-mix(in oklab, var(--color-state-danger) 35%, transparent);
	}
</style>
