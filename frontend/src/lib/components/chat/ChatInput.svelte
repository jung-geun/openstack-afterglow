<script lang="ts">
	import type { ModelCapabilities } from '$lib/api/chatTree';
	import { effortLabel, effortOptionsFor } from '$lib/api/chatEffort';
	import ModelCapabilityBadges from './ModelCapabilityBadges.svelte';

	interface Props {
		value: string;
		streaming?: boolean;
		disabled?: boolean;
		placeholder?: string;
		/** 현재 모델 능력 — effort 선택기·배지·첨부 게이팅. */
		modelCaps?: ModelCapabilities | null;
		/** 선택된 thinking effort(null=서버 기본). reasoning 지원 모델만 노출. */
		effort?: string | null;
		onSend: () => void;
		onStop: () => void;
	}
	let {
		value = $bindable(''),
		streaming = false,
		disabled = false,
		placeholder = '메시지를 입력하세요  (Enter 전송 · Shift+Enter 줄바꿈)',
		modelCaps = null,
		effort = $bindable(null),
		onSend,
		onStop
	}: Props = $props();

	let ta = $state<HTMLTextAreaElement | null>(null);
	let effortOpen = $state(false);

	const effortOptions = $derived(effortOptionsFor(modelCaps));
	const showEffort = $derived(effortOptions.length > 0);

	// 내용에 맞춰 높이 자동 조절(최대 12rem)
	function autoGrow() {
		const el = ta;
		if (!el) return;
		el.style.height = 'auto';
		el.style.height = `${Math.min(el.scrollHeight, 192)}px`;
	}
	$effect(() => {
		void value;
		autoGrow();
	});

	function onKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
			e.preventDefault();
			if (!streaming) onSend();
		}
	}

	function chooseEffort(v: string | null) {
		effort = v;
		effortOpen = false;
	}

	const canSend = $derived(!disabled && !streaming && value.trim().length > 0);
</script>

<div class="composer">
	<div class="input-wrap">
		<textarea
			bind:this={ta}
			bind:value
			{placeholder}
			rows="1"
			disabled={disabled && !streaming}
			onkeydown={onKeydown}
			oninput={autoGrow}
		></textarea>

		<div class="toolbar">
			<div class="tb-left">
				<!-- +메뉴(파일·이미지·도구) shell — P3/P4 에서 배선 -->
				<button type="button" class="tool-shell" disabled title="파일·이미지·도구 (준비 중)" aria-label="첨부(준비 중)">
					<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.9" aria-hidden="true"><path d="M12 5v14M5 12h14" stroke-linecap="round" /></svg>
				</button>
				<ModelCapabilityBadges caps={modelCaps} size="sm" />
			</div>

			<div class="tb-right">
				{#if showEffort}
					<div class="effort">
						<button
							type="button"
							class="effort-btn"
							class:on={effort !== null}
							onclick={() => (effortOpen = !effortOpen)}
							aria-haspopup="listbox"
							aria-expanded={effortOpen}
							title="추론 강도"
						>
							<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M9.5 21h5M12 3a6 6 0 0 1 4 10.5c-.6.6-1 1.4-1 2.2V17H9v-1.3c0-.8-.4-1.6-1-2.2A6 6 0 0 1 12 3z" stroke-linecap="round" stroke-linejoin="round" /></svg>
							<span>{effort ? effortLabel(effort) : '추론'}</span>
						</button>
						{#if effortOpen}
							<div class="scrim" role="button" tabindex="-1" aria-label="닫기" onclick={() => (effortOpen = false)} onkeydown={(e) => e.key === 'Escape' && (effortOpen = false)}></div>
							<div class="effort-menu" role="listbox">
								<div class="effort-head">추론 강도</div>
								<button type="button" class="effort-opt" class:sel={effort === null} role="option" aria-selected={effort === null} onclick={() => chooseEffort(null)}>기본</button>
								{#each effortOptions as v (v)}
									<button type="button" class="effort-opt" class:sel={effort === v} role="option" aria-selected={effort === v} onclick={() => chooseEffort(v)}>{effortLabel(v)}</button>
								{/each}
							</div>
						{/if}
					</div>
				{/if}

				{#if streaming}
					<button type="button" class="send stop" onclick={onStop} title="생성 중단" aria-label="생성 중단">
						<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><rect x="7" y="7" width="10" height="10" rx="1.5" /></svg>
					</button>
				{:else}
					<button type="button" class="send" disabled={!canSend} onclick={onSend} title="전송" aria-label="전송">
						<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 19V5M5 12l7-7 7 7" stroke-linecap="round" stroke-linejoin="round" /></svg>
					</button>
				{/if}
			</div>
		</div>
	</div>
	<p class="hint">AI 응답은 부정확할 수 있습니다. 중요한 내용은 확인하세요.</p>
</div>

<style>
	.composer {
		padding: 0.75rem 1rem 0.9rem;
	}
	.input-wrap {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		padding: 0.6rem 0.7rem 0.55rem;
		border-radius: 1rem;
		border: 1px solid var(--color-line);
		background: var(--color-surface-base);
		transition: border-color 0.15s, box-shadow 0.15s;
	}
	.input-wrap:focus-within {
		border-color: var(--color-accent);
		box-shadow: var(--focus-ring);
	}
	textarea {
		resize: none;
		border: none;
		outline: none;
		background: transparent;
		color: var(--color-ink-0);
		font-size: 0.9rem;
		line-height: 1.5;
		max-height: 12rem;
		padding: 0.15rem 0.2rem;
	}
	textarea::placeholder {
		color: var(--color-ink-3);
	}
	.toolbar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
	}
	.tb-left {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		min-width: 0;
		overflow: hidden;
	}
	.tb-right {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		flex-shrink: 0;
	}
	.tool-shell {
		flex-shrink: 0;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 1.9rem;
		height: 1.9rem;
		border-radius: 0.55rem;
		border: 1px solid var(--color-line);
		background: transparent;
		color: var(--color-ink-3);
		cursor: not-allowed;
		opacity: 0.6;
	}
	.effort {
		position: relative;
	}
	.effort-btn {
		display: inline-flex;
		align-items: center;
		gap: 0.28rem;
		padding: 0.32rem 0.6rem;
		border-radius: 0.55rem;
		border: 1px solid var(--color-line);
		background: var(--color-surface-sunken);
		color: var(--color-ink-2);
		font-size: 0.74rem;
		font-weight: 600;
		cursor: pointer;
		white-space: nowrap;
	}
	.effort-btn:hover {
		color: var(--color-ink-0);
		border-color: var(--color-line-2);
	}
	.effort-btn.on {
		color: color-mix(in oklab, #a855f7 70%, var(--color-ink-1));
		border-color: color-mix(in oklab, #a855f7 40%, var(--color-line));
	}
	.scrim {
		position: fixed;
		inset: 0;
		z-index: 20;
		border: none;
		background: transparent;
	}
	.effort-menu {
		position: absolute;
		bottom: calc(100% + 0.3rem);
		right: 0;
		z-index: 21;
		min-width: 8rem;
		background: var(--color-surface-raised);
		border: 1px solid var(--color-line);
		border-radius: 0.6rem;
		box-shadow: 0 10px 28px color-mix(in oklab, var(--color-ink-0) 20%, transparent);
		padding: 0.3rem;
		display: flex;
		flex-direction: column;
		gap: 0.08rem;
	}
	.effort-head {
		padding: 0.3rem 0.55rem;
		font-size: 0.66rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.03em;
		color: var(--color-ink-3);
	}
	.effort-opt {
		text-align: left;
		padding: 0.4rem 0.55rem;
		border: none;
		border-radius: 0.4rem;
		background: transparent;
		color: var(--color-ink-1);
		font-size: 0.8rem;
		cursor: pointer;
	}
	.effort-opt:hover {
		background: var(--color-surface-sunken);
	}
	.effort-opt.sel {
		color: var(--color-accent);
		font-weight: 600;
	}
	.send {
		flex-shrink: 0;
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 2.1rem;
		height: 2.1rem;
		border-radius: 0.7rem;
		border: none;
		background: var(--color-accent);
		color: var(--color-action-on-accent);
		cursor: pointer;
		transition: filter 0.15s, background 0.15s, opacity 0.15s;
	}
	.send:hover:not(:disabled) {
		filter: brightness(1.08);
	}
	.send:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}
	.send.stop {
		background: var(--color-surface-sunken);
		color: var(--color-ink-0);
		border: 1px solid var(--color-line);
	}
	.send.stop:hover {
		background: var(--color-surface-raised);
	}
	.hint {
		margin: 0.5rem 0 0;
		text-align: center;
		font-size: 0.6875rem;
		color: var(--color-ink-3);
	}
</style>
