<script lang="ts">
	interface Props {
		count: number;
		busy?: boolean;
		onStart: () => void;
		onStop: () => void;
		onDelete: () => void;
		onClear: () => void;
	}

	let { count, busy = false, onStart, onStop, onDelete, onClear }: Props = $props();
</script>

{#if count > 0}
	<div class="bulk-overlay-wrap" role="region" aria-label="선택한 인스턴스 일괄 작업">
		<div class="bulk-overlay-panel">
			<div class="bulk-count" aria-live="polite"><strong>{count}</strong>개 선택됨</div>
			<div class="bulk-actions">
				<button type="button" class="bulk-btn bulk-start" disabled={busy} onclick={onStart}>시작</button>
				<button type="button" class="bulk-btn bulk-stop" disabled={busy} onclick={onStop}>종료</button>
				<button type="button" class="bulk-btn bulk-delete" disabled={busy} onclick={onDelete}>삭제</button>
				<button type="button" class="bulk-btn bulk-clear" onclick={onClear}>취소</button>
			</div>
		</div>
	</div>
{/if}

<style>
	.bulk-overlay-wrap {
		position: fixed;
		left: 50%;
		bottom: max(1.25rem, env(safe-area-inset-bottom));
		z-index: 60;
		width: min(760px, calc(100vw - 2rem));
		transform: translateX(-50%);
		pointer-events: none;
	}

	.bulk-overlay-panel {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		padding: 0.875rem 1rem;
		border: 1px solid color-mix(in oklab, var(--color-accent-2) 34%, transparent);
		border-radius: 1.125rem;
		background:
			linear-gradient(135deg, color-mix(in oklab, var(--color-accent-2) 20%, transparent), transparent 42%),
			color-mix(in oklab, var(--color-surface-raised) 90%, transparent);
		box-shadow:
			0 18px 60px color-mix(in oklab, black 32%, transparent),
			0 0 0 1px color-mix(in oklab, white 7%, transparent) inset;
		backdrop-filter: blur(14px) saturate(1.15);
		pointer-events: auto;
		animation: bulk-rise 0.18s ease;
	}

	.bulk-count {
		color: var(--color-accent);
		font-size: 0.9375rem;
		font-weight: 700;
		letter-spacing: -0.01em;
		white-space: nowrap;
	}

	.bulk-count strong {
		font-size: 1.2em;
	}

	.bulk-actions {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
		justify-content: flex-end;
	}

	.bulk-btn {
		border: 0;
		border-radius: 0.75rem;
		padding: 0.55rem 0.85rem;
		color: white;
		font-size: 0.8125rem;
		font-weight: 800;
		letter-spacing: -0.01em;
		box-shadow: 0 8px 22px color-mix(in oklab, black 22%, transparent);
		cursor: pointer;
		transition:
			transform 0.14s ease,
			filter 0.14s ease,
			opacity 0.14s ease;
	}

	.bulk-btn:hover:not(:disabled) {
		transform: translateY(-1px);
		filter: brightness(1.08);
	}

	.bulk-btn:focus-visible {
		outline: none;
		box-shadow: var(--focus-ring);
	}

	.bulk-btn:disabled {
		cursor: wait;
		opacity: 0.55;
	}

	.bulk-start { background: linear-gradient(135deg, var(--color-state-success), color-mix(in oklab, var(--color-state-success) 74%, black)); }
	.bulk-stop { background: linear-gradient(135deg, var(--color-state-warning), color-mix(in oklab, var(--color-state-warning) 74%, black)); }
	.bulk-delete { background: linear-gradient(135deg, var(--color-state-danger), color-mix(in oklab, var(--color-state-danger) 74%, black)); }
	.bulk-clear { background: linear-gradient(135deg, var(--color-state-neutral), color-mix(in oklab, var(--color-state-neutral) 74%, black)); }

	@keyframes bulk-rise {
		from {
			opacity: 0;
			transform: translateY(10px) scale(0.98);
		}
		to {
			opacity: 1;
			transform: translateY(0) scale(1);
		}
	}

	@media (max-width: 640px) {
		.bulk-overlay-panel {
			align-items: stretch;
			flex-direction: column;
		}

		.bulk-actions {
			justify-content: stretch;
		}

		.bulk-btn {
			flex: 1 1 calc(50% - 0.25rem);
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.bulk-overlay-panel {
			animation: none;
		}
		.bulk-btn {
			transition: none;
		}
	}
</style>
