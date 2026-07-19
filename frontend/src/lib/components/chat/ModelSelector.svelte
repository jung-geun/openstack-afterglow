<script lang="ts">
	interface AvailableModel {
		model_name: string;
		display_name: string;
	}
	interface Props {
		models: AvailableModel[];
		value?: string;
		onSelect: (modelName: string) => void;
		/** 컴팩트: 재생성 인라인용 아이콘 트리거 */
		compact?: boolean;
		disabled?: boolean;
		placeholder?: string;
		align?: 'left' | 'right';
	}
	let {
		models,
		value = '',
		onSelect,
		compact = false,
		disabled = false,
		placeholder = '모델 선택',
		align = 'left'
	}: Props = $props();

	let open = $state(false);
	let root = $state<HTMLDivElement | null>(null);

	const current = $derived(models.find((m) => m.model_name === value) ?? null);
	const label = $derived(current?.display_name ?? placeholder);

	function toggle() {
		if (disabled || models.length === 0) return;
		open = !open;
	}
	function choose(name: string) {
		open = false;
		onSelect(name);
	}
	function onWindowClick(e: MouseEvent) {
		if (root && !root.contains(e.target as Node)) open = false;
	}
	function onKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') open = false;
	}
</script>

<svelte:window onclick={onWindowClick} onkeydown={onKeydown} />

<div class="model-selector" class:compact bind:this={root}>
	<button
		type="button"
		class="trigger"
		class:compact
		{disabled}
		aria-haspopup="listbox"
		aria-expanded={open}
		title={compact ? '다른 모델로 재생성' : label}
		onclick={toggle}
	>
		{#if compact}
			<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8">
				<path d="M4 4v6h6M20 20v-6h-6" stroke-linecap="round" stroke-linejoin="round" />
				<path d="M20 10a8 8 0 0 0-14.9-3M4 14a8 8 0 0 0 14.9 3" stroke-linecap="round" stroke-linejoin="round" />
			</svg>
		{:else}
			<span class="trigger-label">{label}</span>
			<svg class="chev" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
				<path d="M6 9l6 6 6-6" stroke-linecap="round" stroke-linejoin="round" />
			</svg>
		{/if}
	</button>

	{#if open}
		<ul class="menu" class:right={align === 'right'} role="listbox">
			{#if models.length === 0}
				<li class="empty">사용 가능한 모델 없음</li>
			{:else}
				{#each models as m (m.model_name)}
					<li>
						<button
							type="button"
							role="option"
							aria-selected={m.model_name === value}
							class="item"
							class:active={m.model_name === value}
							onclick={() => choose(m.model_name)}
						>
							<span class="item-label">{m.display_name}</span>
							{#if m.model_name === value}
								<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.2">
									<path d="M20 6L9 17l-5-5" stroke-linecap="round" stroke-linejoin="round" />
								</svg>
							{/if}
						</button>
					</li>
				{/each}
			{/if}
		</ul>
	{/if}
</div>

<style>
	.model-selector {
		position: relative;
		display: inline-block;
	}
	.trigger {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		max-width: 100%;
		padding: 0.4rem 0.6rem;
		border-radius: 0.5rem;
		border: 1px solid var(--color-line);
		background: var(--color-surface-base);
		color: var(--color-ink-1);
		font-size: 0.8125rem;
		cursor: pointer;
		transition: background 0.15s, border-color 0.15s, color 0.15s;
	}
	.trigger:hover:not(:disabled) {
		background: var(--color-surface-sunken);
		border-color: var(--color-line-2);
		color: var(--color-ink-0);
	}
	.trigger:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
	.trigger.compact {
		padding: 0.25rem;
		border-color: transparent;
		background: transparent;
		color: var(--color-ink-3);
	}
	.trigger.compact:hover:not(:disabled) {
		color: var(--color-ink-0);
		background: var(--color-surface-sunken);
	}
	.trigger-label {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.chev {
		flex-shrink: 0;
		color: var(--color-ink-3);
	}
	.menu {
		position: absolute;
		z-index: 30;
		top: calc(100% + 0.35rem);
		left: 0;
		min-width: 12rem;
		max-width: 18rem;
		max-height: 16rem;
		overflow-y: auto;
		padding: 0.3rem;
		margin: 0;
		list-style: none;
		border-radius: 0.6rem;
		border: 1px solid var(--color-line);
		background: var(--color-surface-raised);
		box-shadow: 0 12px 32px rgba(0, 0, 0, 0.28);
	}
	.menu.right {
		left: auto;
		right: 0;
	}
	.item {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.6rem;
		width: 100%;
		padding: 0.45rem 0.55rem;
		border-radius: 0.4rem;
		background: transparent;
		border: none;
		text-align: left;
		font-size: 0.8125rem;
		color: var(--color-ink-1);
		cursor: pointer;
		transition: background 0.12s, color 0.12s;
	}
	.item:hover {
		background: var(--color-surface-sunken);
		color: var(--color-ink-0);
	}
	.item.active {
		color: var(--color-accent);
	}
	.item-label {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.empty {
		padding: 0.5rem 0.55rem;
		font-size: 0.8125rem;
		color: var(--color-ink-3);
	}
</style>
