<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import { confirmDialog } from '$lib/stores/confirm.svelte';
	import { toast } from '$lib/stores/toast';
	import Modal from '$lib/components/ui/Modal.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import {
		buildWorkspacePayload,
		emptyWorkspaceForm,
		workspaceToForm,
		type Workspace,
		type WorkspaceForm
	} from '$lib/api/chatWorkspaces';

	interface Props {
		open: boolean;
		onClose: () => void;
		onChanged?: () => void;
	}
	let { open, onClose, onChanged }: Props = $props();

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	let workspaces = $state<Workspace[]>([]);
	let loading = $state(true);
	let mode = $state<'list' | 'form'>('list');
	let editingId = $state<number | null>(null);
	let form = $state<WorkspaceForm>(emptyWorkspaceForm());
	let saving = $state(false);

	const canSubmit = $derived(form.name.trim().length > 0 && !saving);

	async function load() {
		if (!token) return;
		loading = true;
		try {
			workspaces = await api.get<Workspace[]>('/api/v1/chat/workspaces', token, projectId);
		} catch {
			toast.error('프로젝트 목록을 불러오지 못했습니다');
		} finally {
			loading = false;
		}
	}

	// 모달이 열릴 때 로드하고 목록 뷰로 초기화
	$effect(() => {
		if (open) {
			mode = 'list';
			editingId = null;
			void load();
		}
	});

	function startCreate() {
		form = emptyWorkspaceForm();
		editingId = null;
		mode = 'form';
	}
	function startEdit(w: Workspace) {
		form = workspaceToForm(w);
		editingId = w.id;
		mode = 'form';
	}

	async function submit() {
		if (!token || !canSubmit) return;
		saving = true;
		try {
			const payload = buildWorkspacePayload(form);
			if (editingId !== null) {
				await api.patch(`/api/v1/chat/workspaces/${editingId}`, payload, token, projectId);
				toast.success('프로젝트를 수정했습니다');
			} else {
				await api.post('/api/v1/chat/workspaces', payload, token, projectId);
				toast.success('프로젝트를 생성했습니다');
			}
			mode = 'list';
			await load();
			onChanged?.();
		} catch (e) {
			toast.error(e instanceof ApiError ? e.message : '저장에 실패했습니다');
		} finally {
			saving = false;
		}
	}

	async function remove(w: Workspace) {
		if (!token) return;
		if (!(await confirmDialog(`'${w.name}' 프로젝트를 삭제하시겠습니까? 대화는 미분류로 이동합니다.`)))
			return;
		try {
			await api.delete(`/api/v1/chat/workspaces/${w.id}`, token, projectId);
			await load();
			onChanged?.();
			toast.success('삭제했습니다');
		} catch {
			toast.error('삭제에 실패했습니다');
		}
	}
</script>

<Modal {open} {onClose}>
	<div class="panel">
		<header class="head">
			<div class="head-title">
				{#if mode === 'form'}
					<button type="button" class="back" onclick={() => (mode = 'list')} aria-label="목록으로">
						<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6" stroke-linecap="round" stroke-linejoin="round" /></svg>
					</button>
					<h2>{editingId !== null ? '프로젝트 편집' : '새 프로젝트'}</h2>
				{:else}
					<h2>내 프로젝트</h2>
				{/if}
			</div>
			<button type="button" class="close" onclick={onClose} aria-label="닫기">
				<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 6l12 12M18 6L6 18" stroke-linecap="round" /></svg>
			</button>
		</header>

		<div class="body">
			{#if mode === 'form'}
				<form
					class="builder"
					onsubmit={(e) => {
						e.preventDefault();
						if (canSubmit) submit();
					}}
				>
					<label class="field">
						<span class="lbl">이름 <span class="req">*</span></span>
						<input class="inp" bind:value={form.name} maxlength="100" placeholder="프로젝트 이름" required />
					</label>
					<label class="field">
						<span class="lbl">설명</span>
						<input class="inp" bind:value={form.description} maxlength="500" placeholder="이 프로젝트에 대한 짧은 설명" />
					</label>
					<label class="field">
						<span class="lbl">공통 지침 <span class="hint">이 프로젝트의 모든 대화에 적용</span></span>
						<textarea class="inp ta" bind:value={form.instructions} rows="6" maxlength="20000" placeholder="예: 답변은 항상 한국어로, 코드에는 주석을 달아라."></textarea>
					</label>
					<div class="actions">
						<Button variant="ghost" type="button" onclick={() => (mode = 'list')}>취소</Button>
						<Button variant="accent" type="submit" disabled={!canSubmit}>
							{saving ? '저장 중…' : editingId !== null ? '변경 저장' : '프로젝트 생성'}
						</Button>
					</div>
				</form>
			{:else if loading}
				<p class="muted">불러오는 중…</p>
			{:else}
				<div class="list-head">
					<span class="muted">{workspaces.length}개</span>
					<Button variant="accent" size="sm" onclick={startCreate}>+ 새 프로젝트</Button>
				</div>
				{#if workspaces.length === 0}
					<div class="empty-box">
						<p>아직 프로젝트가 없습니다.</p>
						<p class="muted">관련된 대화를 프로젝트로 묶고 공통 지침을 지정하세요.</p>
					</div>
				{:else}
					<div class="cards">
						{#each workspaces as w (w.id)}
							<div class="card">
								<span class="icon">
									<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" stroke-linejoin="round" /></svg>
								</span>
								<div class="card-main">
									<div class="name truncate">{w.name}</div>
									{#if w.description}<div class="desc truncate">{w.description}</div>{/if}
								</div>
								<div class="card-actions">
									<button type="button" class="act" onclick={() => startEdit(w)} title="편집" aria-label="편집">
										<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z" stroke-linecap="round" stroke-linejoin="round" /></svg>
									</button>
									<button type="button" class="act danger" onclick={() => remove(w)} title="삭제" aria-label="삭제">
										<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 7h16M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2M6 7l1 13a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-13" stroke-linecap="round" stroke-linejoin="round" /></svg>
									</button>
								</div>
							</div>
						{/each}
					</div>
				{/if}
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
	.head-title {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.head-title h2 {
		margin: 0;
		font-size: 0.95rem;
		font-weight: 650;
		color: var(--color-ink-0);
	}
	.back,
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
	.back:hover,
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
	.list-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 0.75rem;
	}
	.empty-box {
		padding: 2.5rem 1rem;
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
		align-items: center;
		gap: 0.75rem;
		padding: 0.7rem 0.85rem;
		border-radius: 0.65rem;
		border: 1px solid var(--color-line);
		background: var(--color-surface-base);
	}
	.icon {
		flex-shrink: 0;
		width: 2.4rem;
		height: 2.4rem;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 0.6rem;
		background: var(--color-surface-sunken);
		border: 1px solid var(--color-line);
		color: var(--color-ink-2);
	}
	.card-main {
		flex: 1;
		min-width: 0;
	}
	.name {
		font-size: 0.875rem;
		font-weight: 600;
		color: var(--color-ink-0);
	}
	.desc {
		font-size: 0.78rem;
		color: var(--color-ink-3);
		margin-top: 0.1rem;
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
	.truncate {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.builder {
		display: flex;
		flex-direction: column;
		gap: 0.9rem;
	}
	.field {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		min-width: 0;
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
	.req {
		color: var(--color-state-danger);
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
		min-height: 6rem;
		line-height: 1.5;
		font-family: inherit;
	}
	.actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.5rem;
		padding-top: 0.3rem;
	}
</style>
