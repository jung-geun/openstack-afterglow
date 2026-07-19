<script lang="ts">
	interface Props {
		value: string;
		streaming?: boolean;
		disabled?: boolean;
		placeholder?: string;
		onSend: () => void;
		onStop: () => void;
	}
	let {
		value = $bindable(''),
		streaming = false,
		disabled = false,
		placeholder = '메시지를 입력하세요  (Enter 전송 · Shift+Enter 줄바꿈)',
		onSend,
		onStop
	}: Props = $props();

	let ta = $state<HTMLTextAreaElement | null>(null);

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

		{#if streaming}
			<button type="button" class="send stop" onclick={onStop} title="생성 중단" aria-label="생성 중단">
				<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
					<rect x="7" y="7" width="10" height="10" rx="1.5" />
				</svg>
			</button>
		{:else}
			<button
				type="button"
				class="send"
				disabled={!canSend}
				onclick={onSend}
				title="전송"
				aria-label="전송"
			>
				<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
					<path d="M12 19V5M5 12l7-7 7 7" stroke-linecap="round" stroke-linejoin="round" />
				</svg>
			</button>
		{/if}
	</div>
	<p class="hint">AI 응답은 부정확할 수 있습니다. 중요한 내용은 확인하세요.</p>
</div>

<style>
	.composer {
		padding: 0.75rem 1rem 0.9rem;
	}
	.input-wrap {
		position: relative;
		display: flex;
		align-items: flex-end;
		gap: 0.5rem;
		padding: 0.55rem 0.55rem 0.55rem 0.9rem;
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
		flex: 1;
		resize: none;
		border: none;
		outline: none;
		background: transparent;
		color: var(--color-ink-0);
		font-size: 0.9rem;
		line-height: 1.5;
		max-height: 12rem;
		padding: 0.25rem 0;
	}
	textarea::placeholder {
		color: var(--color-ink-3);
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
