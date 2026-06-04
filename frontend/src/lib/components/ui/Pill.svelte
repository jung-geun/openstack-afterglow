<script lang="ts">
  type Tone = 'accent' | 'warm' | 'success' | 'warning' | 'danger' | 'info' | 'neutral' | 'admin-tone';

  interface Props {
    tone?: Tone;
    class?: string;
    children: import('svelte').Snippet;
  }

  let { tone = 'neutral', class: className = '', children }: Props = $props();
</script>

<span class="pill pill-{tone} {className}">
  {@render children()}
</span>

<style>
  .pill {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 500;
    border: 1px solid transparent;
    line-height: 1.6;
    white-space: nowrap;
  }

  .pill-accent {
    background: color-mix(in oklab, var(--color-accent) 14%, transparent);
    color: var(--color-accent);
    border-color: color-mix(in oklab, var(--color-accent) 30%, transparent);
  }
  .pill-warm {
    background: color-mix(in oklab, var(--color-warm) 14%, transparent);
    color: var(--color-warm);
    border-color: color-mix(in oklab, var(--color-warm) 30%, transparent);
  }
  .pill-success {
    background: color-mix(in oklab, var(--color-state-success) 14%, transparent);
    color: var(--color-state-success);
    border-color: color-mix(in oklab, var(--color-state-success) 30%, transparent);
  }
  .pill-warning {
    background: color-mix(in oklab, var(--color-state-warning) 14%, transparent);
    color: var(--color-state-warning);
    border-color: color-mix(in oklab, var(--color-state-warning) 30%, transparent);
  }
  .pill-danger {
    background: color-mix(in oklab, var(--color-state-danger) 14%, transparent);
    color: var(--color-state-danger);
    border-color: color-mix(in oklab, var(--color-state-danger) 30%, transparent);
  }
  .pill-info {
    background: color-mix(in oklab, var(--color-state-info) 14%, transparent);
    color: var(--color-state-info);
    border-color: color-mix(in oklab, var(--color-state-info) 30%, transparent);
  }
  .pill-neutral {
    background: color-mix(in oklab, var(--color-state-neutral) 14%, transparent);
    color: var(--color-state-neutral);
    border-color: color-mix(in oklab, var(--color-state-neutral) 30%, transparent);
  }
  .pill-admin-tone {
    background: var(--admin-tone-soft);
    color: var(--admin-tone);
    border-color: var(--admin-tone-ring);
  }
</style>
