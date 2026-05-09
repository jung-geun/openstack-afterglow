<script lang="ts">
  import { getStatusStyle } from '$lib/config/statusColors';

  interface Props {
    status: string | null | undefined;
    class?: string;
  }

  let { status, class: className = '' }: Props = $props();

  const s = $derived(getStatusStyle(status));
</script>

<span class="chip chip-{s.tone} {className}" class:pulse={s.pulse}>
  <span class="dot"></span>
  <span class="label">{status ?? '—'}</span>
</span>

<style>
  .chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 2px 10px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 500;
    border: 1px solid transparent;
    line-height: 1.6;
    max-width: 100%;
  }

  .label {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .dot {
    width: 6px;
    height: 6px;
    border-radius: 999px;
    background: currentColor;
    flex-shrink: 0;
  }

  .chip-success {
    background: color-mix(in oklab, var(--color-state-success) 14%, transparent);
    color: var(--color-state-success);
    border-color: color-mix(in oklab, var(--color-state-success) 30%, transparent);
  }
  .chip-warning {
    background: color-mix(in oklab, var(--color-state-warning) 14%, transparent);
    color: var(--color-state-warning);
    border-color: color-mix(in oklab, var(--color-state-warning) 30%, transparent);
  }
  .chip-danger {
    background: color-mix(in oklab, var(--color-state-danger) 14%, transparent);
    color: var(--color-state-danger);
    border-color: color-mix(in oklab, var(--color-state-danger) 30%, transparent);
  }
  .chip-info {
    background: color-mix(in oklab, var(--color-state-info) 14%, transparent);
    color: var(--color-state-info);
    border-color: color-mix(in oklab, var(--color-state-info) 30%, transparent);
  }
  .chip-neutral {
    background: color-mix(in oklab, var(--color-state-neutral) 14%, transparent);
    color: var(--color-state-neutral);
    border-color: color-mix(in oklab, var(--color-state-neutral) 30%, transparent);
  }

  .pulse .dot {
    animation: pulse 1.4s ease-in-out infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0.35; }
  }
</style>
