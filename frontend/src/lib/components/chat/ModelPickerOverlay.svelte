<script lang="ts">
	import type { AvailableModel } from '$lib/api/chatTree';
	import ModelCapabilityBadges from './ModelCapabilityBadges.svelte';

	interface Props {
		open: boolean;
		models: AvailableModel[];
		value: string;
		onSelect: (modelName: string) => void;
		onClose: () => void;
	}
	let { open, models, value, onSelect, onClose }: Props = $props();

	let query = $state('');

	interface Group {
		provider: string;
		models: AvailableModel[];
	}
	const grouped = $derived.by((): Group[] => {
		const q = query.trim().toLowerCase();
		const match = (m: AvailableModel) =>
			!q ||
			m.display_name.toLowerCase().includes(q) ||
			m.model_name.toLowerCase().includes(q) ||
			(m.provider ?? '').toLowerCase().includes(q);
		const byProvider = new Map<string, AvailableModel[]>();
		for (const m of models) {
			if (!match(m)) continue;
			const key = m.provider ?? '기타';
			const arr = byProvider.get(key);
			if (arr) arr.push(m);
			else byProvider.set(key, [m]);
		}
		return [...byProvider.entries()].map(([provider, models]) => ({ provider, models }));
	});
	const total = $derived(grouped.reduce((n, g) => n + g.models.length, 0));

	function pick(m: AvailableModel) {
		onSelect(m.model_name);
		onClose();
	}
</script>

{#if open}
	<div
		class="overlay"
		role="button"
		tabindex="-1"
		aria-label="닫기"
		onclick={onClose}
		onkeydown={(e) => e.key === 'Escape' && onClose()}
	></div>
	<div class="panel" role="dialog" aria-label="모델 선택">
		<header class="head">
			<h2>모델 선택</h2>
			<button type="button" class="close" onclick={onClose} aria-label="닫기">
				<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M18 6L6 18M6 6l12 12" stroke-linecap="round" /></svg>
			</button>
		</header>

		<div class="search">
			<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" stroke-linecap="round" /></svg>
			<!-- svelte-ignore a11y_autofocus -->
			<input type="text" placeholder="모델 검색 (이름·프로바이더)" bind:value={query} autofocus />
		</div>

		<div class="list">
			{#if total === 0}
				<p class="empty">검색 결과가 없습니다</p>
			{:else}
				{#each grouped as g (g.provider)}
					<div class="group-label">{g.provider}</div>
					{#each g.models as m (m.model_name)}
						<button
							type="button"
							class="model-row"
							class:active={m.model_name === value}
							onclick={() => pick(m)}
						>
							<div class="model-main">
								<span class="model-name">{m.display_name}</span>
								{#if m.model_name !== m.display_name}
									<span class="model-id">{m.model_name}</span>
								{/if}
							</div>
							<ModelCapabilityBadges caps={m.capabilities} size="xs" />
							{#if m.model_name === value}
								<svg class="check" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true"><path d="M20 6L9 17l-5-5" stroke-linecap="round" stroke-linejoin="round" /></svg>
							{/if}
						</button>
					{/each}
				{/each}
			{/if}
		</div>
	</div>
{/if}

<style>
	.overlay {
		position: fixed;
		inset: 0;
		background: color-mix(in oklab, var(--color-ink-0) 55%, transparent);
		z-index: 50;
		border: none;
	}
	.panel {
		position: fixed;
		inset: 50% auto auto 50%;
		transform: translate(-50%, -50%);
		width: min(46rem, 94vw);
		height: min(80vh, 44rem);
		background: var(--color-surface-base);
		border: 1px solid var(--color-line);
		border-radius: 1rem;
		z-index: 51;
		display: flex;
		flex-direction: column;
		box-shadow: 0 24px 64px color-mix(in oklab, var(--color-ink-0) 30%, transparent);
		overflow: hidden;
	}
	.head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 1rem 1.1rem 0.7rem;
	}
	.head h2 {
		margin: 0;
		font-size: 1.05rem;
		font-weight: 650;
		color: var(--color-ink-0);
	}
	.close {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 2rem;
		height: 2rem;
		border-radius: 0.45rem;
		border: none;
		background: transparent;
		color: var(--color-ink-3);
		cursor: pointer;
	}
	.close:hover {
		background: var(--color-surface-sunken);
		color: var(--color-ink-0);
	}
	.search {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin: 0 1.1rem 0.6rem;
		padding: 0.6rem 0.8rem;
		border-radius: 0.7rem;
		border: 1px solid var(--color-line);
		background: var(--color-surface-sunken);
		color: var(--color-ink-3);
	}
	.search input {
		flex: 1;
		border: none;
		outline: none;
		background: transparent;
		color: var(--color-ink-0);
		font-size: 0.9rem;
	}
	.search input::placeholder {
		color: var(--color-ink-3);
	}
	.list {
		flex: 1;
		min-height: 0;
		overflow-y: auto;
		padding: 0 0.6rem 0.8rem;
	}
	.empty {
		padding: 2rem;
		text-align: center;
		color: var(--color-ink-3);
		font-size: 0.85rem;
	}
	.group-label {
		padding: 0.7rem 0.6rem 0.35rem;
		font-size: 0.7rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--color-ink-3);
	}
	.model-row {
		display: flex;
		align-items: center;
		gap: 0.7rem;
		width: 100%;
		padding: 0.6rem 0.7rem;
		border: 1px solid transparent;
		border-radius: 0.6rem;
		background: transparent;
		cursor: pointer;
		text-align: left;
	}
	.model-row:hover {
		background: var(--color-surface-sunken);
	}
	.model-row.active {
		background: var(--color-surface-raised);
		border-color: var(--color-accent);
	}
	.model-main {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: 0.1rem;
	}
	.model-name {
		font-size: 0.88rem;
		font-weight: 600;
		color: var(--color-ink-0);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.model-id {
		font-size: 0.72rem;
		color: var(--color-ink-3);
		font-family: var(--font-mono, ui-monospace, monospace);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.check {
		flex-shrink: 0;
		color: var(--color-accent);
	}
</style>
