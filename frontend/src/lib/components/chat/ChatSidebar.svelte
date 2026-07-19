<script lang="ts">
	interface Conversation {
		id: string;
		title: string | null;
		model_name: string | null;
		updated_at: string | null;
	}
	interface Props {
		conversations: Conversation[];
		activeConvId: string | null;
		tempMode?: boolean;
		busy?: boolean;
		onSelect: (conv: Conversation) => void;
		onNew: () => void;
		onTempChat: () => void;
		onDelete: (conv: Conversation) => void;
	}
	let {
		conversations,
		activeConvId,
		tempMode = false,
		busy = false,
		onSelect,
		onNew,
		onTempChat,
		onDelete
	}: Props = $props();

	let query = $state('');
	const filtered = $derived(
		query.trim()
			? conversations.filter((c) =>
					(c.title ?? '새 대화').toLowerCase().includes(query.trim().toLowerCase())
				)
			: conversations
	);
</script>

<aside class="sidebar">
	<div class="top">
		<button type="button" class="new-btn" disabled={busy} onclick={onNew}>
			<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14" stroke-linecap="round" /></svg>
			새 채팅
		</button>
		<button
			type="button"
			class="temp-btn"
			class:active={tempMode}
			disabled={busy}
			onclick={onTempChat}
			title="저장되지 않는 임시 채팅"
			aria-pressed={tempMode}
		>
			<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 8v4l2.5 2.5M12 3a9 9 0 1 0 9 9" stroke-linecap="round" stroke-linejoin="round" /></svg>
		</button>
	</div>

	<div class="search">
		<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" stroke-linecap="round" /></svg>
		<input type="text" placeholder="대화 검색" bind:value={query} />
	</div>

	<div class="list">
		{#if filtered.length === 0}
			<p class="empty">{conversations.length === 0 ? '대화가 없습니다' : '검색 결과 없음'}</p>
		{:else}
			{#each filtered as conv (conv.id)}
				<div class="item-row" class:active={!tempMode && activeConvId === conv.id}>
					<button type="button" class="item" disabled={busy} onclick={() => onSelect(conv)}>
						<span class="item-title">{conv.title || '새 대화'}</span>
					</button>
					<button
						type="button"
						class="del"
						disabled={busy}
						onclick={() => onDelete(conv)}
						title="대화 삭제"
						aria-label="대화 삭제"
					>
						<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 7h16M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2M6 7l1 13a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-13" stroke-linecap="round" stroke-linejoin="round" /></svg>
					</button>
				</div>
			{/each}
		{/if}
	</div>

	<div class="foot">
		<a class="tools-link" href="/dashboard/chat/tools">
			<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18v3h3l6.3-6.3a4 4 0 0 0 5.4-5.4l-2.5 2.5-2.5-2.5 2.5-2.5z" stroke-linejoin="round" /></svg>
			내 도구 관리 (MCP·툴)
		</a>
	</div>
</aside>

<style>
	.sidebar {
		width: 16rem;
		flex-shrink: 0;
		display: flex;
		flex-direction: column;
		min-height: 0;
		border-right: 1px solid var(--color-line);
		background: var(--color-surface-sunken);
	}
	.top {
		display: flex;
		gap: 0.4rem;
		padding: 0.75rem 0.75rem 0.5rem;
	}
	.new-btn {
		flex: 1;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 0.4rem;
		padding: 0.55rem 0.75rem;
		border-radius: 0.6rem;
		border: 1px solid var(--color-line);
		background: var(--color-surface-base);
		color: var(--color-ink-0);
		font-size: 0.8125rem;
		font-weight: 550;
		cursor: pointer;
		transition: background 0.15s, border-color 0.15s;
	}
	.new-btn:hover:not(:disabled) {
		background: var(--color-surface-raised);
		border-color: var(--color-line-2);
	}
	.temp-btn {
		flex-shrink: 0;
		width: 2.35rem;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		border-radius: 0.6rem;
		border: 1px solid var(--color-line);
		background: var(--color-surface-base);
		color: var(--color-ink-2);
		cursor: pointer;
		transition: background 0.15s, color 0.15s, border-color 0.15s;
	}
	.temp-btn:hover:not(:disabled) {
		color: var(--color-ink-0);
		border-color: var(--color-line-2);
	}
	.temp-btn.active {
		background: var(--color-accent);
		color: var(--color-action-on-accent);
		border-color: var(--color-accent);
	}
	.search {
		display: flex;
		align-items: center;
		gap: 0.45rem;
		margin: 0 0.75rem 0.5rem;
		padding: 0.45rem 0.6rem;
		border-radius: 0.55rem;
		border: 1px solid var(--color-line);
		background: var(--color-surface-base);
		color: var(--color-ink-3);
	}
	.search input {
		flex: 1;
		border: none;
		outline: none;
		background: transparent;
		color: var(--color-ink-1);
		font-size: 0.8125rem;
	}
	.search input::placeholder {
		color: var(--color-ink-3);
	}
	.list {
		flex: 1;
		min-height: 0;
		overflow-y: auto;
		padding: 0 0.5rem;
		display: flex;
		flex-direction: column;
		gap: 0.1rem;
	}
	.empty {
		padding: 1rem 0.75rem;
		font-size: 0.78rem;
		color: var(--color-ink-3);
	}
	.item-row {
		display: flex;
		align-items: center;
		border-radius: 0.5rem;
		transition: background 0.12s;
	}
	.item-row:hover {
		background: var(--color-surface-base);
	}
	.item-row.active {
		background: var(--color-surface-raised);
	}
	.item {
		flex: 1;
		min-width: 0;
		text-align: left;
		padding: 0.5rem 0.6rem;
		border: none;
		background: transparent;
		color: var(--color-ink-2);
		font-size: 0.8125rem;
		cursor: pointer;
	}
	.item-row.active .item {
		color: var(--color-ink-0);
	}
	.item-title {
		display: block;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.del {
		flex-shrink: 0;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 1.9rem;
		height: 1.9rem;
		margin-right: 0.2rem;
		border: none;
		border-radius: 0.4rem;
		background: transparent;
		color: var(--color-ink-3);
		cursor: pointer;
		opacity: 0;
		transition: opacity 0.12s, color 0.12s, background 0.12s;
	}
	.item-row:hover .del {
		opacity: 1;
	}
	.del:hover:not(:disabled) {
		color: var(--color-state-danger);
		background: color-mix(in oklab, var(--color-state-danger) 12%, transparent);
	}
	.foot {
		padding: 0.6rem 0.75rem;
		border-top: 1px solid var(--color-line);
	}
	.tools-link {
		display: inline-flex;
		align-items: center;
		gap: 0.45rem;
		width: 100%;
		font-size: 0.78rem;
		color: var(--color-ink-3);
		text-decoration: none;
		transition: color 0.15s;
	}
	.tools-link:hover {
		color: var(--color-ink-1);
	}
</style>
