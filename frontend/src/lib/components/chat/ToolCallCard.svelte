<script lang="ts">
	import { formatToolArgs, type ToolActivityItem } from '$lib/api/chatToolActivity';

	interface Props {
		item: ToolActivityItem;
	}
	let { item }: Props = $props();

	let open = $state(false);
	const argsText = $derived(formatToolArgs(item.args));
	const hasDetail = $derived(Boolean(argsText) || Boolean(item.result));
</script>

<div class="tool-card" class:running={item.running}>
	<button
		type="button"
		class="tool-head"
		onclick={() => (open = !open)}
		disabled={!hasDetail}
		aria-expanded={open}
	>
		{#if item.running}
			<span class="spinner" aria-hidden="true"></span>
		{:else}
			<svg class="ic" viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.9" aria-hidden="true">
				<path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18v3h3l6.3-6.3a4 4 0 0 0 5.4-5.4l-2.5 2.5-2.5-2.5 2.5-2.5z" stroke-linejoin="round" />
			</svg>
		{/if}
		<span class="tool-name">{item.name}</span>
		<span class="tool-status">{item.running ? '실행 중…' : '완료'}</span>
		{#if hasDetail}
			<svg class="chevron" class:open viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
				<path d="M6 9l6 6 6-6" stroke-linecap="round" stroke-linejoin="round" />
			</svg>
		{/if}
	</button>

	{#if open && hasDetail}
		<div class="tool-detail">
			{#if argsText}
				<div class="detail-block">
					<div class="detail-label">입력</div>
					<pre class="detail-pre">{argsText}</pre>
				</div>
			{/if}
			{#if item.result}
				<div class="detail-block">
					<div class="detail-label">결과</div>
					<pre class="detail-pre">{item.result}</pre>
				</div>
			{/if}
		</div>
	{/if}
</div>

<style>
	.tool-card {
		border: 1px solid var(--color-line);
		border-radius: 0.6rem;
		background: var(--color-surface-sunken);
		overflow: hidden;
		font-size: 0.76rem;
	}
	.tool-head {
		display: flex;
		align-items: center;
		gap: 0.45rem;
		width: 100%;
		padding: 0.45rem 0.6rem;
		background: transparent;
		border: none;
		color: var(--color-ink-2);
		cursor: pointer;
		text-align: left;
	}
	.tool-head:disabled {
		cursor: default;
	}
	.tool-head:not(:disabled):hover {
		background: var(--color-surface-raised);
	}
	.ic {
		flex-shrink: 0;
		color: var(--color-accent);
	}
	.tool-name {
		font-weight: 600;
		color: var(--color-ink-1);
		font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, monospace);
	}
	.tool-status {
		color: var(--color-ink-3);
		font-size: 0.7rem;
	}
	.chevron {
		margin-left: auto;
		color: var(--color-ink-3);
		transition: transform 0.15s;
	}
	.chevron.open {
		transform: rotate(180deg);
	}
	.tool-detail {
		border-top: 1px solid var(--color-line);
		padding: 0.5rem 0.6rem;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	.detail-label {
		font-size: 0.66rem;
		text-transform: uppercase;
		letter-spacing: 0.03em;
		color: var(--color-ink-3);
		margin-bottom: 0.2rem;
	}
	.detail-pre {
		margin: 0;
		padding: 0.45rem 0.55rem;
		border-radius: 0.4rem;
		background: var(--color-surface-base);
		border: 1px solid var(--color-line);
		font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, monospace);
		font-size: 0.72rem;
		line-height: 1.5;
		white-space: pre-wrap;
		word-break: break-word;
		overflow-wrap: anywhere;
		max-height: 16rem;
		overflow-y: auto;
		color: var(--color-ink-1);
	}
	.spinner {
		flex-shrink: 0;
		width: 0.8rem;
		height: 0.8rem;
		border-radius: 50%;
		border: 2px solid var(--color-line-2);
		border-top-color: var(--color-accent);
		animation: spin 0.8s linear infinite;
	}
	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}
</style>
