<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import { confirmDialog } from '$lib/stores/confirm.svelte';
	import { toast } from '$lib/stores/toast';
	import Modal from '$lib/components/ui/Modal.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import type { Memory } from '$lib/api/chatWorkspaces';

	interface Props {
		open: boolean;
		onClose: () => void;
	}
	let { open, onClose }: Props = $props();

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	let memories = $state<Memory[]>([]);
	let loading = $state(true);
	let editingId = $state<number | null>(null); // null = 새 항목 작성 중
	let draft = $state('');
	let saving = $state(false);

	const canSubmit = $derived(draft.trim().length > 0 && !saving);

	async function load() {
		if (!token) return;
		loading = true;
		try {
			memories = await api.get<Memory[]>('/api/v1/chat/memories', token, projectId);
		} catch {
			toast.error('메모리를 불러오지 못했습니다');
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		if (open) {
			editingId = null;
			draft = '';
			void load();
		}
	});

	function startEdit(m: Memory) {
		editingId = m.id;
		draft = m.content;
	}
	function cancelEdit() {
		editingId = null;
		draft = '';
	}

	async function submit() {
		if (!token || !canSubmit) return;
		saving = true;
		try {
			const content = draft.trim();
			if (editingId !== null) {
				await api.patch(`/api/v1/chat/memories/${editingId}`, { content }, token, projectId);
				toast.success('메모리를 수정했습니다');
			} else {
				await api.post('/api/v1/chat/memories', { content }, token, projectId);
				toast.success('메모리를 추가했습니다');
			}
			editingId = null;
			draft = '';
			await load();
		} catch (e) {
			toast.error(e instanceof ApiError ? e.message : '저장에 실패했습니다');
		} finally {
			saving = false;
		}
	}

	async function toggleActive(m: Memory) {
		if (!token) return;
		try {
			await api.patch(`/api/v1/chat/memories/${m.id}`, { is_active: !m.is_active }, token, projectId);
			await load();
		} catch {
			toast.error('상태 변경에 실패했습니다');
		}
	}

	async function remove(m: Memory) {
		if (!token) return;
		if (!(await confirmDialog('이 메모리를 삭제하시겠습니까?'))) return;
		try {
			await api.delete(`/api/v1/chat/memories/${m.id}`, token, projectId);
			if (editingId === m.id) cancelEdit();
			await load();
			toast.success('삭제했습니다');
		} catch {
			toast.error('삭제에 실패했습니다');
		}
	}
</script>

<Modal {open} {onClose}>
	<div class="panel">
		<header class="head">
			<h2>메모리</h2>
			<button type="button" class="close" onclick={onClose} aria-label="닫기">
				<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 6l12 12M18 6L6 18" stroke-linecap="round" /></svg>
			</button>
		</header>

		<div class="body">
			<form
				class="composer"
				onsubmit={(e) => {
					e.preventDefault();
					if (canSubmit) submit();
				}}
			>
				<span class="lbl">
					{editingId !== null ? '메모리 편집' : '새 메모리'}
					<span class="hint">AI 가 나에 대해 기억할 내용</span>
				</span>
				<textarea
					class="inp ta"
					bind:value={draft}
					rows="3"
					maxlength="4000"
					placeholder="예: 나는 SvelteKit + TypeScript 로 개발한다. 답변은 간결하게."
				></textarea>
				<div class="composer-actions">
					{#if editingId !== null}
						<Button variant="ghost" size="sm" type="button" onclick={cancelEdit}>취소</Button>
					{/if}
					<Button variant="accent" size="sm" type="submit" disabled={!canSubmit}>
						{saving ? '저장 중…' : editingId !== null ? '변경 저장' : '+ 추가'}
					</Button>
				</div>
			</form>

			<div class="divider"></div>

			{#if loading}
				<p class="muted">불러오는 중…</p>
			{:else if memories.length === 0}
				<div class="empty-box">
					<p>아직 저장된 메모리가 없습니다.</p>
					<p class="muted">자주 반복하는 선호·컨텍스트를 메모리로 남겨 두세요.</p>
				</div>
			{:else}
				<div class="cards">
					{#each memories as m (m.id)}
						<div class="card" class:inactive={!m.is_active}>
							<div class="card-main">
								<p class="content">{m.content}</p>
								{#if !m.is_active}<span class="off-badge">비활성</span>{/if}
							</div>
							<div class="card-actions">
								<button
									type="button"
									class="act"
									onclick={() => toggleActive(m)}
									title={m.is_active ? '비활성화' : '활성화'}
									aria-label={m.is_active ? '비활성화' : '활성화'}
								>
									{#if m.is_active}
										<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M20 6L9 17l-5-5" stroke-linecap="round" stroke-linejoin="round" /></svg>
									{:else}
										<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="9" /></svg>
									{/if}
								</button>
								<button type="button" class="act" onclick={() => startEdit(m)} title="편집" aria-label="편집">
									<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z" stroke-linecap="round" stroke-linejoin="round" /></svg>
								</button>
								<button type="button" class="act danger" onclick={() => remove(m)} title="삭제" aria-label="삭제">
									<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 7h16M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2M6 7l1 13a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-13" stroke-linecap="round" stroke-linejoin="round" /></svg>
								</button>
							</div>
						</div>
					{/each}
				</div>
			{/if}
		</div>
	</div>
</Modal>

<style>
	.panel {
		width: min(94vw, 40rem);
		max-height: 88vh;
		display: flex;
		flex-direction: column;
		border-radius: 0.9rem;
		border: 1px solid var(--color-line);
		background: var(--color-surface-raised);
		box-shadow: 0 24px 64px rgba(0, 0, 0, 0.4);
		overflow: hidden;
	}
	.head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.9rem 1.1rem;
		border-bottom: 1px solid var(--color-line);
	}
	.head h2 {
		margin: 0;
		font-size: 0.95rem;
		font-weight: 650;
		color: var(--color-ink-0);
	}
	.close {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 2rem;
		height: 2rem;
		border: none;
		border-radius: 0.5rem;
		background: transparent;
		color: var(--color-ink-3);
		cursor: pointer;
		transition: background 0.12s, color 0.12s;
	}
	.close:hover {
		background: var(--color-surface-sunken);
		color: var(--color-ink-0);
	}
	.body {
		padding: 1.1rem;
		overflow-y: auto;
	}
	.muted {
		font-size: 0.8rem;
		color: var(--color-ink-3);
	}
	.composer {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}
	.lbl {
		font-size: 0.75rem;
		font-weight: 550;
		color: var(--color-ink-2);
	}
	.hint {
		font-weight: 400;
		color: var(--color-ink-3);
	}
	.inp {
		width: 100%;
		border-radius: 0.5rem;
		border: 1px solid var(--color-line);
		background: var(--color-surface-base);
		padding: 0.5rem 0.65rem;
		font-size: 0.8125rem;
		color: var(--color-ink-1);
	}
	.inp:focus {
		outline: none;
		border-color: var(--color-accent);
	}
	.ta {
		resize: vertical;
		min-height: 3.5rem;
		line-height: 1.5;
		font-family: inherit;
	}
	.composer-actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.5rem;
	}
	.divider {
		height: 1px;
		background: var(--color-line);
		margin: 1rem 0;
	}
	.empty-box {
		padding: 2rem 1rem;
		text-align: center;
	}
	.empty-box p {
		margin: 0.2rem 0;
		font-size: 0.85rem;
		color: var(--color-ink-1);
	}
	.cards {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	.card {
		display: flex;
		align-items: flex-start;
		gap: 0.75rem;
		padding: 0.7rem 0.85rem;
		border-radius: 0.65rem;
		border: 1px solid var(--color-line);
		background: var(--color-surface-base);
	}
	.card.inactive {
		opacity: 0.6;
	}
	.card-main {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: 0.3rem;
	}
	.content {
		margin: 0;
		font-size: 0.8125rem;
		line-height: 1.5;
		color: var(--color-ink-1);
		white-space: pre-wrap;
		word-break: break-word;
	}
	.off-badge {
		align-self: flex-start;
		font-size: 0.68rem;
		padding: 0.1rem 0.4rem;
		border-radius: 999px;
		background: var(--color-surface-sunken);
		color: var(--color-ink-3);
	}
	.card-actions {
		display: flex;
		gap: 0.15rem;
		flex-shrink: 0;
	}
	.act {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 1.9rem;
		height: 1.9rem;
		border: none;
		border-radius: 0.45rem;
		background: transparent;
		color: var(--color-ink-3);
		cursor: pointer;
		transition: background 0.12s, color 0.12s;
	}
	.act:hover {
		background: var(--color-surface-sunken);
		color: var(--color-ink-0);
	}
	.act.danger:hover {
		color: var(--color-state-danger);
		background: color-mix(in oklab, var(--color-state-danger) 12%, transparent);
	}
</style>
