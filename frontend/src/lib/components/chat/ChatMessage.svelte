<script lang="ts">
	import MarkdownMessage from './MarkdownMessage.svelte';
	import ModelSelector from './ModelSelector.svelte';
	import ToolCallCard from './ToolCallCard.svelte';
	import ThinkingBlock from './ThinkingBlock.svelte';
	import type { AvailableModel, ChatMessage } from '$lib/api/chatTree';
	import { formatMetrics, type StreamMetrics } from '$lib/api/chatMetrics';
	import {
		parseAssistantToolCalls,
		toolNameFromResultMeta,
		type ToolActivityItem
	} from '$lib/api/chatToolActivity';
	import { citationDomain, citationLabel, normalizeCitations } from '$lib/api/chatCitations';

	interface Props {
		message: ChatMessage & { streaming?: boolean };
		models: AvailableModel[];
		/** 생성 속도 계측(tok/s). 없으면 미표시. */
		metrics?: StreamMetrics | null;
		/** 라이브 스트리밍 중 누적된 도구 실행 아이템(draft 전용). */
		toolItems?: ToolActivityItem[];
		/** 추론(thinking) 텍스트 — 있으면 접이식 블록 노출(라이브, 미저장). */
		reasoning?: string;
		/** 형제 버전 정보 (index/total). total>1 이면 ‹ n/m › 노출 */
		siblingIndex?: number;
		siblingTotal?: number;
		/** 스트리밍 중 여부(액션 숨김) */
		busy?: boolean;
		/** 에이전트 바인딩 중 — 모델 선택 대신 단순 재생성만 */
		modelLocked?: boolean;
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
		metrics = null,
		toolItems = [],
		reasoning = '',
		siblingIndex = 1,
		siblingTotal = 1,
		busy = false,
		modelLocked = false,
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
	// 추론은 본문 토큰이 시작되면 끝난다 — 스트리밍 중이라도 content 가 있으면 "추론 중"이 아니다.
	const reasoningActive = $derived(streaming && message.content.length === 0);
	const metricsText = $derived(formatMetrics(metrics));
	// 저장된 assistant 호출 스텝(재로딩) → 호출 카드(인자). role=tool → 결과 카드.
	const invocationItems = $derived(
		!isUser && !isTool ? parseAssistantToolCalls(message.tool_calls) : []
	);
	const citations = $derived(!isUser && !isTool ? normalizeCitations(message.citations) : []);
	const toolResultItem = $derived<ToolActivityItem | null>(
		isTool
			? {
					id: null,
					name: toolNameFromResultMeta(message.tool_calls) ?? '도구',
					args: null,
					result: message.content,
					running: false
				}
			: null
	);
	let copied = $state(false);

	function copy() {
		onCopy(message.content);
		copied = true;
		setTimeout(() => (copied = false), 1400);
	}
</script>

{#if isTool}
	<!-- 툴 결과 메시지 → 접이식 결과 카드 -->
	<div class="row assistant">
		<div class="tool-wrap">
			{#if toolResultItem}
				<ToolCallCard item={toolResultItem} />
			{/if}
		</div>
	</div>
{:else}
	<div class="row" class:user={isUser} class:assistant={!isUser}>
		<div class="bubble" class:user={isUser} class:assistant={!isUser}>
			{#if isUser}
				<div class="user-text">{message.content}</div>
			{:else}
				{#if reasoning}
					<ThinkingBlock text={reasoning} active={reasoningActive} />
				{/if}
				{#if toolItems.length || invocationItems.length}
					<div class="tool-cards">
						{#each toolItems as t (t.id ?? t.name)}
							<ToolCallCard item={t} />
						{/each}
						{#each invocationItems as t (t.id ?? t.name)}
							<ToolCallCard item={t} />
						{/each}
					</div>
				{/if}
				<MarkdownMessage content={message.content} {streaming} />
				{#if streaming && message.content.length === 0}
					<div class="thinking">
						<span></span><span></span><span></span>
					</div>
				{/if}
				{#if streaming && metricsText}
					<div class="live-metric" aria-live="off">{metricsText}</div>
				{/if}
				{#if citations.length}
					<div class="sources">
						<div class="sources-label">
							<svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1" stroke-linecap="round" stroke-linejoin="round" /></svg>
							출처 {citations.length}
						</div>
						<ol class="sources-list">
							{#each citations as c, i (c.url + i)}
								<li>
									<a href={c.url} target="_blank" rel="noopener noreferrer nofollow" title={c.url}>
										<span class="src-num">{i + 1}</span>
										<span class="src-label">{citationLabel(c)}</span>
										<span class="src-domain">{citationDomain(c.url)}</span>
									</a>
								</li>
							{/each}
						</ol>
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
					{#if modelLocked}
						<!-- 에이전트 바인딩 중: 모델 선택 없이 단순 재생성 -->
						<button type="button" class="act" disabled={busy} onclick={() => onRegenerate('')} title="재생성" aria-label="재생성">
							<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 4v6h6M20 20v-6h-6" stroke-linecap="round" stroke-linejoin="round" /><path d="M20 10a8 8 0 0 0-14.9-3M4 14a8 8 0 0 0 14.9 3" stroke-linecap="round" stroke-linejoin="round" /></svg>
						</button>
					{:else}
						<ModelSelector {models} value={message.model_name ?? ''} compact disabled={busy} onSelect={onRegenerate} align="left" />
					{/if}
					<button type="button" class="act" disabled={busy} onclick={onFork} title="이 지점에서 분기" aria-label="분기">
						<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="6" cy="6" r="2.5" /><circle cx="6" cy="18" r="2.5" /><circle cx="18" cy="9" r="2.5" /><path d="M6 8.5v3a3 3 0 0 0 3 3h6M18 11.5v.5" stroke-linecap="round" /></svg>
					</button>
					{#if modelDisplayName}
						<span class="model-tag">{modelDisplayName}</span>
					{/if}
					{#if metricsText}
						<span class="metric-tag" title="생성 속도">{metricsText}</span>
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
	.metric-tag {
		font-size: 0.68rem;
		color: var(--color-ink-3);
		padding-left: 0.3rem;
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}
	.live-metric {
		margin-top: 0.35rem;
		font-size: 0.68rem;
		color: var(--color-ink-3);
		font-variant-numeric: tabular-nums;
	}
	.sources {
		margin-top: 0.7rem;
		padding-top: 0.6rem;
		border-top: 1px solid var(--color-line);
	}
	.sources-label {
		display: flex;
		align-items: center;
		gap: 0.3rem;
		font-size: 0.7rem;
		font-weight: 600;
		color: var(--color-ink-3);
		margin-bottom: 0.4rem;
	}
	.sources-list {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.15rem;
	}
	.sources-list a {
		display: flex;
		align-items: baseline;
		gap: 0.45rem;
		padding: 0.28rem 0.4rem;
		border-radius: 0.4rem;
		text-decoration: none;
		color: var(--color-ink-1);
		font-size: 0.78rem;
	}
	.sources-list a:hover {
		background: var(--color-surface-sunken);
	}
	.src-num {
		flex-shrink: 0;
		min-width: 1.1rem;
		height: 1.1rem;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		border-radius: 0.3rem;
		background: var(--color-surface-sunken);
		border: 1px solid var(--color-line);
		font-size: 0.64rem;
		color: var(--color-ink-3);
		font-variant-numeric: tabular-nums;
	}
	.src-label {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.src-domain {
		flex-shrink: 0;
		font-size: 0.68rem;
		color: var(--color-ink-3);
	}
	.tool-wrap {
		max-width: min(92%, 52rem);
	}
	.tool-cards {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		margin-bottom: 0.6rem;
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
