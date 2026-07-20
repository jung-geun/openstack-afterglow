<script lang="ts">
	import type { Workspace } from '$lib/api/chatWorkspaces';
	import type { ChatUsage } from '$lib/api/chatTree';
	import { auth } from '$lib/stores/auth';
	import ChatUserMenu from './ChatUserMenu.svelte';

	interface Conversation {
		id: string;
		title: string | null;
		model_name: string | null;
		workspace_id: number | null;
		updated_at: string | null;
	}
	interface Props {
		conversations: Conversation[];
		workspaces: Workspace[];
		activeConvId: string | null;
		tempMode?: boolean;
		busy?: boolean;
		/** 사이드바 열림 여부(데스크톱 접기 / 모바일 드로어). */
		open?: boolean;
		/** 사용자 메뉴 팝오버에 표시할 사용량(우상단 위젯 대체). */
		usage?: ChatUsage | null;
		onSelect: (conv: Conversation) => void;
		onNew: () => void;
		onDelete: (conv: Conversation) => void;
		onAssign: (conv: Conversation, workspaceId: number | null) => void;
		onAgents: () => void;
		onWorkspaces: () => void;
		onSettings: () => void;
	}
	let {
		conversations,
		workspaces,
		activeConvId,
		tempMode = false,
		busy = false,
		open = true,
		usage = null,
		onSelect,
		onNew,
		onDelete,
		onAssign,
		onAgents,
		onWorkspaces,
		onSettings
	}: Props = $props();

	let query = $state('');
	let userMenuOpen = $state(false);

	// 접힌 그룹 키 집합(기본 펼침)
	let collapsed = $state<Record<string, boolean>>({});
	function toggle(key: string) {
		collapsed[key] = !collapsed[key];
	}

	// 제목 드래그앤드롭으로 프로젝트 이동 (Codex식). 드래그 중인 대화 id + drop 대상.
	let draggingId = $state<string | null>(null);
	let dropTargetKey = $state<string | null>(null);
	function onDropTo(workspaceId: number | null) {
		const conv = conversations.find((c) => c.id === draggingId);
		draggingId = null;
		dropTargetKey = null;
		if (conv && conv.workspace_id !== workspaceId) onAssign(conv, workspaceId);
	}

	interface Group {
		key: string;
		id: number | null;
		name: string;
		convs: Conversation[];
	}

	const grouped = $derived.by(() => {
		const q = query.trim().toLowerCase();
		const match = (c: Conversation) => !q || (c.title ?? '새 대화').toLowerCase().includes(q);
		const visible = conversations.filter(match);
		const knownIds = new Set(workspaces.map((w) => w.id));

		// 드래그 중엔 빈 프로젝트도 drop 대상으로 렌더(대화 없는 프로젝트로 이동 가능).
		const wsGroups: Group[] = workspaces
			.map((w) => ({
				key: `ws-${w.id}`,
				id: w.id,
				name: w.name,
				convs: visible.filter((c) => c.workspace_id === w.id)
			}))
			.filter((g) => g.convs.length > 0 || draggingId !== null);

		// workspace_id 가 없거나 알 수 없는(삭제된) 프로젝트를 가리키면 미분류로.
		const unassigned = visible.filter(
			(c) => c.workspace_id == null || !knownIds.has(c.workspace_id)
		);

		return { wsGroups, unassigned, hasGroups: wsGroups.length > 0, total: visible.length };
	});
</script>

<aside class="sidebar" class:closed={!open}>
	<div class="top">
		<button type="button" class="new-btn" disabled={busy} onclick={onNew}>
			<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14" stroke-linecap="round" /></svg>
			새 채팅
		</button>
	</div>

	<div class="search">
		<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" stroke-linecap="round" /></svg>
		<input type="text" placeholder="대화 검색" bind:value={query} />
	</div>

	<div class="list">
		{#if grouped.total === 0}
			<p class="empty">{conversations.length === 0 ? '대화가 없습니다' : '검색 결과 없음'}</p>
		{:else if !grouped.hasGroups}
			{#each grouped.unassigned as conv (conv.id)}
				{@render convRow(conv)}
			{/each}
		{:else}
			{#each grouped.wsGroups as g (g.key)}
				{@render groupHeader(g)}
				{#if !collapsed[g.key]}
					{#each g.convs as conv (conv.id)}
						{@render convRow(conv)}
					{/each}
				{/if}
			{/each}
			{#if grouped.unassigned.length > 0}
				{@render groupHeader({ key: 'none', id: null, name: '미분류', convs: grouped.unassigned })}
				{#if !collapsed['none']}
					{#each grouped.unassigned as conv (conv.id)}
						{@render convRow(conv)}
					{/each}
				{/if}
			{/if}
		{/if}
	</div>

	<div class="entries">
		<button type="button" class="entry" onclick={onWorkspaces}>
			<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" stroke-linejoin="round" /></svg>
			프로젝트
		</button>
		<button type="button" class="entry" onclick={onAgents}>
			<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="4" y="7" width="16" height="12" rx="2" /><path d="M9 7V4h6v3M9 13h.01M15 13h.01" stroke-linecap="round" /></svg>
			에이전트
		</button>
	</div>

	<!-- 좌하단 사용자 버튼 → 사용량·설정 팝오버 (헤더 우상단 사용량 위젯 대체) -->
	<div class="user-bar">
		<button
			type="button"
			class="user-btn"
			onclick={() => (userMenuOpen = !userMenuOpen)}
			aria-haspopup="menu"
			aria-expanded={userMenuOpen}
		>
			<span class="user-avatar">{($auth.username ?? '?').slice(0, 2).toUpperCase()}</span>
			<span class="user-name truncate">{$auth.username || '사용자'}</span>
			<svg class="dots" viewBox="0 0 24 24" width="16" height="16" fill="currentColor" aria-hidden="true"><circle cx="5" cy="12" r="1.6" /><circle cx="12" cy="12" r="1.6" /><circle cx="19" cy="12" r="1.6" /></svg>
		</button>
		<ChatUserMenu
			open={userMenuOpen}
			username={$auth.username}
			{usage}
			onClose={() => (userMenuOpen = false)}
			{onSettings}
		/>
	</div>
</aside>

{#snippet groupHeader(g: Group)}
	<button
		type="button"
		class="group-head"
		class:drop-target={draggingId !== null && dropTargetKey === g.key}
		onclick={() => toggle(g.key)}
		ondragover={(e) => {
			if (draggingId !== null) {
				e.preventDefault();
				dropTargetKey = g.key;
			}
		}}
		ondragleave={() => {
			if (dropTargetKey === g.key) dropTargetKey = null;
		}}
		ondrop={(e) => {
			e.preventDefault();
			onDropTo(g.id);
		}}
		aria-expanded={!collapsed[g.key]}
	>
		<svg class="chev" class:collapsed={collapsed[g.key]} viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6" stroke-linecap="round" stroke-linejoin="round" /></svg>
		<span class="group-name truncate">{g.name}</span>
		<span class="group-count">{g.convs.length}</span>
	</button>
{/snippet}

{#snippet convRow(conv: Conversation)}
	<div
		class="item-row"
		class:active={!tempMode && activeConvId === conv.id}
		class:dragging={draggingId === conv.id}
		draggable={!busy}
		ondragstart={() => (draggingId = conv.id)}
		ondragend={() => {
			draggingId = null;
			dropTargetKey = null;
		}}
	>
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
{/snippet}

<style>
	.sidebar {
		width: 16rem;
		flex-shrink: 0;
		display: flex;
		flex-direction: column;
		min-height: 0;
		border-right: 1px solid var(--color-line);
		background: var(--color-surface-sunken);
		transition: margin-left 0.22s ease;
	}
	/* 데스크톱: 접으면 왼쪽으로 밀어내 본문이 전체 폭을 차지 */
	.sidebar.closed {
		margin-left: -16rem;
	}
	/* 모바일: 오버레이 드로어 — 흐름에서 빼내 본문은 항상 전체 폭, 열릴 때만 위에 겹침 */
	@media (max-width: 768px) {
		.sidebar {
			position: absolute;
			top: 0;
			bottom: 0;
			left: 0;
			z-index: 40;
			box-shadow: 2px 0 16px color-mix(in oklab, var(--color-ink-0) 18%, transparent);
		}
		.sidebar.closed {
			margin-left: -17rem; /* 그림자까지 완전히 숨김 */
		}
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
	.group-head {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		width: 100%;
		padding: 0.4rem 0.5rem;
		margin-top: 0.25rem;
		border: none;
		background: transparent;
		color: var(--color-ink-3);
		font-size: 0.7rem;
		font-weight: 650;
		text-transform: uppercase;
		letter-spacing: 0.03em;
		cursor: pointer;
	}
	.group-head:hover {
		color: var(--color-ink-1);
	}
	.chev {
		flex-shrink: 0;
		transition: transform 0.15s;
	}
	.chev.collapsed {
		transform: rotate(-90deg);
	}
	.group-name {
		flex: 1;
		min-width: 0;
		text-align: left;
	}
	.group-count {
		flex-shrink: 0;
		color: var(--color-ink-3);
		font-weight: 550;
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
	.item-row[draggable='true'] {
		cursor: grab;
	}
	.item-row.dragging {
		opacity: 0.45;
	}
	.group-head.drop-target {
		background: color-mix(in oklab, var(--color-accent) 16%, transparent);
		color: var(--color-accent);
		border-radius: 0.5rem;
		outline: 1px dashed var(--color-accent);
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
	.item-row:hover .del,
	.item-row:focus-within .del {
		opacity: 1;
	}
	.del:hover:not(:disabled) {
		color: var(--color-state-danger);
		background: color-mix(in oklab, var(--color-state-danger) 12%, transparent);
	}
	.entries {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		padding-top: 0.5rem;
		margin: 0.25rem 0.75rem 0.75rem;
		border-top: 1px solid var(--color-line);
	}
	.entry {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 0.7rem;
		border-radius: 0.6rem;
		border: 1px solid var(--color-line);
		background: var(--color-surface-base);
		color: var(--color-ink-1);
		font-size: 0.8125rem;
		font-weight: 550;
		cursor: pointer;
		transition: background 0.15s, color 0.15s, border-color 0.15s;
	}
	.entry:hover {
		background: var(--color-surface-raised);
		color: var(--color-ink-0);
		border-color: var(--color-line-2);
	}
	.user-bar {
		position: relative;
		margin: 0 0.75rem 0.75rem;
	}
	.user-btn {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		width: 100%;
		padding: 0.45rem 0.55rem;
		border-radius: 0.6rem;
		border: 1px solid var(--color-line);
		background: var(--color-surface-base);
		color: var(--color-ink-1);
		cursor: pointer;
		transition: background 0.15s, border-color 0.15s;
	}
	.user-btn:hover {
		background: var(--color-surface-raised);
		border-color: var(--color-line-2);
	}
	.user-avatar {
		flex-shrink: 0;
		width: 1.7rem;
		height: 1.7rem;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		border-radius: 50%;
		background: var(--color-accent);
		color: var(--color-action-on-accent);
		font-size: 0.66rem;
		font-weight: 700;
	}
	.user-name {
		flex: 1;
		min-width: 0;
		text-align: left;
		font-size: 0.8125rem;
		font-weight: 550;
	}
	.dots {
		flex-shrink: 0;
		color: var(--color-ink-3);
	}
	.truncate {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
</style>
