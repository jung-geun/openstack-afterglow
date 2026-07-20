<script lang="ts">
	import type { Workspace } from '$lib/api/chatWorkspaces';

	interface Props {
		workspaces: Workspace[];
		/** 현재 대화(또는 예약된 신규 대화)의 workspace id. null = 미분류. */
		currentWorkspaceId: number | null;
		disabled?: boolean;
		onChange: (workspaceId: number | null) => void;
	}
	let { workspaces, currentWorkspaceId, disabled = false, onChange }: Props = $props();

	let open = $state(false);
	const current = $derived(workspaces.find((w) => w.id === currentWorkspaceId) ?? null);

	function choose(id: number | null) {
		open = false;
		if (id !== currentWorkspaceId) onChange(id);
	}
</script>

<div class="wsp">
	<button
		type="button"
		class="trigger"
		{disabled}
		onclick={() => (open = !open)}
		aria-haspopup="listbox"
		aria-expanded={open}
		title="이 대화의 프로젝트"
	>
		<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" stroke-linejoin="round" /></svg>
		<span class="label">{current?.name ?? '미분류'}</span>
		<svg class="chev" class:open viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M6 9l6 6 6-6" stroke-linecap="round" stroke-linejoin="round" /></svg>
	</button>

	{#if open}
		<div class="scrim" role="button" tabindex="-1" aria-label="닫기" onclick={() => (open = false)} onkeydown={(e) => e.key === 'Escape' && (open = false)}></div>
		<div class="menu" role="listbox">
			<button type="button" class="opt" class:sel={currentWorkspaceId === null} role="option" aria-selected={currentWorkspaceId === null} onclick={() => choose(null)}>
				미분류
			</button>
			{#each workspaces as w (w.id)}
				<button type="button" class="opt" class:sel={currentWorkspaceId === w.id} role="option" aria-selected={currentWorkspaceId === w.id} onclick={() => choose(w.id)}>
					{w.name}
				</button>
			{/each}
		</div>
	{/if}
</div>

<style>
	.wsp {
		position: relative;
		display: inline-block;
	}
	.trigger {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
		padding: 0.25rem 0.55rem;
		border-radius: 0.5rem;
		border: 1px solid var(--color-line);
		background: var(--color-surface-sunken);
		color: var(--color-ink-2);
		font-size: 0.72rem;
		font-weight: 550;
		cursor: pointer;
		transition: border-color 0.12s, color 0.12s;
	}
	.trigger:hover:not(:disabled) {
		color: var(--color-ink-0);
		border-color: var(--color-line-2);
	}
	.trigger:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
	.label {
		max-width: 12rem;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.chev {
		transition: transform 0.12s;
	}
	.chev.open {
		transform: rotate(180deg);
	}
	.scrim {
		position: fixed;
		inset: 0;
		z-index: 20;
		border: none;
		background: transparent;
	}
	.menu {
		position: absolute;
		bottom: calc(100% + 0.3rem);
		left: 0;
		z-index: 21;
		min-width: 11rem;
		max-height: 16rem;
		overflow-y: auto;
		background: var(--color-surface-raised);
		border: 1px solid var(--color-line);
		border-radius: 0.6rem;
		box-shadow: 0 10px 28px color-mix(in oklab, var(--color-ink-0) 20%, transparent);
		padding: 0.3rem;
		display: flex;
		flex-direction: column;
		gap: 0.1rem;
	}
	.opt {
		text-align: left;
		padding: 0.4rem 0.55rem;
		border: none;
		border-radius: 0.4rem;
		background: transparent;
		color: var(--color-ink-1);
		font-size: 0.8rem;
		cursor: pointer;
		white-space: nowrap;
	}
	.opt:hover {
		background: var(--color-surface-sunken);
	}
	.opt.sel {
		color: var(--color-accent);
		font-weight: 600;
	}
</style>
