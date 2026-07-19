<script lang="ts">
	import MarkdownMessage from './MarkdownMessage.svelte';
	import ModelSelector from './ModelSelector.svelte';
	import type { ChatMessage } from '$lib/api/chatTree';

	interface AvailableModel {
		model_name: string;
		display_name: string;
	}
	interface Props {
		message: ChatMessage & { streaming?: boolean };
		models: AvailableModel[];
		/** 형제 버전 정보 (index/total). total>1 이면 ‹ n/m › 노출 */
		siblingIndex?: number;
		siblingTotal?: number;
		/** 스트리밍 중 여부(액션 숨김) */
		busy?: boolean;
		modelDisplayName?: string | null;
		onCopy: (text: string) => void;
		onRegenerate: (modelName: string) => void;
		onFork: () => void;
		onPrevVersion: () => void;
		onNextVersion: () => void;
	}
	let {
		message,
		models,
		siblingIndex = 1,
		siblingTotal = 1,
		busy = false,
		modelDisplayName = null,
		onCopy,
		onRegenerate,
		onFork,
		onPrevVersion,
		onNextVersion
	}: Props = $props();

	const isUser = $derived(message.role === 'user');
	const isTool = $derived(message.role === 'tool');
	const streaming = $derived(Boolean(message.streaming));
	let copied = $state(false);

	function copy() {
		onCopy(message.content);
		copied = true;
		setTimeout(() => (copied = false), 1400);
	}
</script>

{#if isTool}
	<!-- 툴 메시지는 본문 대신 축약 뱃지로 -->
	<div class="row assistant">
		<div class="tool-badge" title={message.content}>
			<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.8">
				<path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18v3h3l6.3-6.3a4 4 0 0 0 5.4-5.4l-2.5 2.5-2.5-2.5 2.5-2.5z" stroke-linejoin="round" />
			</svg>
			<span>도구 사용됨</span>
		</div>
	</div>
{:else}
	<div class="row" class:user={isUser} class:assistant={!isUser}>
		<div class="bubble" class:user={isUser} class:assistant={!isUser}>
			{#if isUser}
				<div class="user-text">{message.content}</div>
			{:else}
				<MarkdownMessage content={message.content} {streaming} />
				{#if streaming && message.content.length === 0}
					<div class="thinking">
						<span></span><span></span><span></span>
					</div>
				{/if}
			{/if}
		</div>

		{#if !streaming}
			<div class="actions" class:user={isUser}>
				{#if siblingTotal > 1}
					<div class="versions">
						<button type="button" class="ver-arrow" disabled={siblingIndex <= 1 || busy} onclick={onPrevVersion} aria-label="이전 버전" title="이전 버전">
							<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M15 18l-6-6 6-6" stroke-linecap="round" stroke-linejoin="round" /></svg>
						</button>
						<span class="ver-count">{siblingIndex}/{siblingTotal}</span>
						<button type="button" class="ver-arrow" disabled={siblingIndex >= siblingTotal || busy} onclick={onNextVersion} aria-label="다음 버전" title="다음 버전">
							<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M9 6l6 6-6 6" stroke-linecap="round" stroke-linejoin="round" /></svg>
						</button>
					</div>
				{/if}

				<button type="button" class="act" onclick={copy} title="복사" aria-label="복사">
					{#if copied}
						<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6L9 17l-5-5" stroke-linecap="round" stroke-linejoin="round" /></svg>
					{:else}
						<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="9" y="9" width="11" height="11" rx="2" /><path d="M5 15V5a2 2 0 0 1 2-2h10" /></svg>
					{/if}
				</button>

				{#if !isUser}
					<ModelSelector {models} value={message.model_name ?? ''} compact disabled={busy} onSelect={onRegenerate} align="left" />
					<button type="button" class="act" disabled={busy} onclick={onFork} title="이 지점에서 분기" aria-label="분기">
						<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="6" cy="6" r="2.5" /><circle cx="6" cy="18" r="2.5" /><circle cx="18" cy="9" r="2.5" /><path d="M6 8.5v3a3 3 0 0 0 3 3h6M18 11.5v.5" stroke-linecap="round" /></svg>
					</button>
					{#if modelDisplayName}
						<span class="model-tag">{modelDisplayName}</span>
					{/if}
				{/if}
			</div>
		{/if}
	</div>
{/if}

<style>
	.row {
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
		max-width: 100%;
	}
	.row.user {
		align-items: flex-end;
	}
	.row.assistant {
		align-items: flex-start;
	}
	.bubble {
		max-width: min(85%, 46rem);
		border-radius: 1.1rem;
		padding: 0.7rem 1rem;
	}
	.bubble.user {
		background: var(--color-accent);
		color: var(--color-action-on-accent);
		border-bottom-right-radius: 0.35rem;
	}
	.bubble.assistant {
		max-width: min(92%, 52rem);
		background: var(--color-surface-raised);
		border: 1px solid var(--color-line);
		border-bottom-left-radius: 0.35rem;
	}
	.user-text {
		font-size: 0.9rem;
		line-height: 1.55;
		white-space: pre-wrap;
		word-break: break-word;
		overflow-wrap: anywhere;
	}
	.actions {
		display: flex;
		align-items: center;
		gap: 0.15rem;
		padding: 0 0.2rem;
		opacity: 0;
		transition: opacity 0.15s;
	}
	.row:hover .actions,
	.actions:focus-within {
		opacity: 1;
	}
	.versions {
		display: inline-flex;
		align-items: center;
		gap: 0.1rem;
	}
	.act,
	.ver-arrow {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 1.75rem;
		height: 1.75rem;
		border-radius: 0.45rem;
		border: none;
		background: transparent;
		color: var(--color-ink-3);
		cursor: pointer;
		transition: background 0.12s, color 0.12s;
	}
	.act:hover:not(:disabled),
	.ver-arrow:hover:not(:disabled) {
		background: var(--color-surface-sunken);
		color: var(--color-ink-0);
	}
	.act:disabled,
	.ver-arrow:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}
	.ver-count {
		font-size: 0.7rem;
		color: var(--color-ink-2);
		min-width: 1.9rem;
		text-align: center;
		font-variant-numeric: tabular-nums;
	}
	.model-tag {
		font-size: 0.68rem;
		color: var(--color-ink-3);
		padding-left: 0.3rem;
	}
	.tool-badge {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		padding: 0.25rem 0.6rem;
		border-radius: 999px;
		border: 1px solid var(--color-line);
		background: var(--color-surface-sunken);
		color: var(--color-ink-2);
		font-size: 0.72rem;
	}
	.thinking {
		display: inline-flex;
		gap: 0.28rem;
		padding: 0.35rem 0.1rem;
	}
	.thinking span {
		width: 0.42rem;
		height: 0.42rem;
		border-radius: 50%;
		background: var(--color-ink-3);
		animation: blink 1.2s infinite ease-in-out both;
	}
	.thinking span:nth-child(2) { animation-delay: 0.16s; }
	.thinking span:nth-child(3) { animation-delay: 0.32s; }
	@keyframes blink {
		0%, 80%, 100% { opacity: 0.25; }
		40% { opacity: 1; }
	}
</style>
