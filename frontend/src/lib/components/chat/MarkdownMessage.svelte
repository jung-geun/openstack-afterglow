<script lang="ts">
	import { renderMarkdown, highlightCodeBlocks } from '$lib/api/chatMarkdown';

	interface Props {
		content: string;
		/** 스트리밍 중이면 코드 하이라이트를 미룬다(델타마다 재하이라이트 방지). */
		streaming?: boolean;
	}
	let { content, streaming = false }: Props = $props();

	let host = $state<HTMLDivElement | null>(null);
	const html = $derived(renderMarkdown(content));

	// 스트리밍이 끝나고 최종 HTML 이 DOM 에 반영된 뒤 한 번만 하이라이트.
	$effect(() => {
		void html;
		const el = host;
		if (!el || streaming) return;
		// 마이크로태스크 이후 DOM 반영 보장
		queueMicrotask(() => {
			if (host) void highlightCodeBlocks(host);
		});
	});
</script>

<div bind:this={host} class="md-body">
	<!-- renderMarkdown 이 DOMPurify.sanitize 로 살균한 HTML -->
	{@html html}
</div>

<style>
	.md-body {
		font-size: 0.875rem;
		line-height: 1.65;
		color: var(--color-ink-1);
		word-break: break-word;
		overflow-wrap: anywhere;
	}
	.md-body :global(p) {
		margin: 0 0 0.75em;
	}
	.md-body :global(p:last-child) {
		margin-bottom: 0;
	}
	.md-body :global(h1),
	.md-body :global(h2),
	.md-body :global(h3),
	.md-body :global(h4) {
		margin: 1.1em 0 0.5em;
		font-weight: 650;
		line-height: 1.3;
		color: var(--color-ink-0);
	}
	.md-body :global(h1) { font-size: 1.35em; }
	.md-body :global(h2) { font-size: 1.2em; }
	.md-body :global(h3) { font-size: 1.05em; }
	.md-body :global(ul),
	.md-body :global(ol) {
		margin: 0 0 0.75em;
		padding-left: 1.4em;
	}
	.md-body :global(li) {
		margin: 0.2em 0;
	}
	.md-body :global(li > p) {
		margin: 0;
	}
	.md-body :global(a) {
		color: var(--color-accent);
		text-decoration: underline;
		text-underline-offset: 2px;
	}
	.md-body :global(a:hover) {
		color: color-mix(in oklab, var(--color-accent) 75%, var(--color-ink-0));
	}
	.md-body :global(blockquote) {
		margin: 0 0 0.75em;
		padding: 0.25em 0 0.25em 0.9em;
		border-left: 3px solid var(--color-line-2);
		color: var(--color-ink-2);
	}
	.md-body :global(hr) {
		border: none;
		border-top: 1px solid var(--color-line);
		margin: 1.2em 0;
	}
	/* 인라인 코드 */
	.md-body :global(:not(pre) > code) {
		font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, monospace);
		font-size: 0.85em;
		padding: 0.12em 0.38em;
		border-radius: 0.35rem;
		background: var(--color-surface-sunken);
		border: 1px solid var(--color-line);
		color: var(--color-ink-0);
	}
	/* 코드 블록(하이라이트 전/후 공통 셸) */
	.md-body :global(pre) {
		margin: 0 0 0.75em;
		padding: 0.85rem 1rem;
		border-radius: 0.6rem;
		border: 1px solid var(--color-line);
		background: var(--color-surface-sunken);
		overflow-x: auto;
		font-size: 0.82em;
		line-height: 1.55;
	}
	.md-body :global(pre code) {
		font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, monospace);
		background: none;
		border: none;
		padding: 0;
		color: var(--color-ink-1);
	}
	/* shiki dual-theme: 기본(다크)은 --shiki-dark, 라이트 모드에서 --shiki-light */
	.md-body :global(pre.shiki),
	.md-body :global(pre.shiki span) {
		color: var(--shiki-dark, inherit);
		background-color: var(--shiki-dark-bg, transparent);
	}
	:global(:root.light) .md-body :global(pre.shiki),
	:global(:root.light) .md-body :global(pre.shiki span) {
		color: var(--shiki-light, inherit);
		background-color: var(--shiki-light-bg, transparent);
	}
	.md-body :global(table) {
		border-collapse: collapse;
		margin: 0 0 0.75em;
		font-size: 0.9em;
		display: block;
		overflow-x: auto;
	}
	.md-body :global(th),
	.md-body :global(td) {
		border: 1px solid var(--color-line);
		padding: 0.35em 0.65em;
		text-align: left;
	}
	.md-body :global(th) {
		background: var(--color-surface-sunken);
		font-weight: 600;
	}
	.md-body :global(img) {
		max-width: 100%;
		border-radius: 0.5rem;
	}
</style>
