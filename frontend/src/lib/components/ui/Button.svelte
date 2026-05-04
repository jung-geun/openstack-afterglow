<script lang="ts">
  import type { Snippet } from 'svelte';

  type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';
  type Size = 'sm' | 'md' | 'lg';

  interface Props {
    variant?: Variant;
    size?: Size;
    type?: 'button' | 'submit' | 'reset';
    disabled?: boolean;
    onclick?: (e: MouseEvent) => void;
    href?: string;
    class?: string;
    children: Snippet;
  }

  let {
    variant = 'primary',
    size = 'md',
    type = 'button',
    disabled,
    onclick,
    href,
    class: className = '',
    children
  }: Props = $props();
</script>

{#if href}
  <a {href} class="btn btn-{variant} btn-{size} {className}">{@render children()}</a>
{:else}
  <button {type} {disabled} {onclick} class="btn btn-{variant} btn-{size} {className}">
    {@render children()}
  </button>
{/if}

<style>
  .btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    border-radius: 8px;
    font-weight: 500;
    transition: all 0.15s;
    border: 1px solid transparent;
    cursor: pointer;
    white-space: nowrap;
  }
  .btn:disabled {
    opacity: 0.45;
    cursor: not-allowed;
    box-shadow: none !important;
    filter: none !important;
  }

  /* Sizes */
  .btn-sm { padding: 4px 10px; font-size: 12px; }
  .btn-md { padding: 7px 14px; font-size: 13px; }
  .btn-lg { padding: 10px 20px; font-size: 14px; }

  /* Variants */
  .btn-primary {
    background: var(--gradient-warm);
    color: white;
    box-shadow: var(--glow-warm);
  }
  .btn-primary:hover:not(:disabled) {
    filter: brightness(1.08);
    box-shadow: 0 10px 28px color-mix(in oklab, var(--color-warm) 35%, transparent);
  }

  .btn-secondary {
    background: var(--color-surface-raised);
    color: var(--color-ink-1);
    border-color: var(--color-line);
  }
  .btn-secondary:hover:not(:disabled) {
    background: var(--color-surface-sunken);
  }

  .btn-ghost {
    background: transparent;
    color: var(--color-ink-2);
  }
  .btn-ghost:hover:not(:disabled) {
    background: var(--color-surface-sunken);
    color: var(--color-ink-0);
  }

  .btn-danger {
    background: color-mix(in oklab, var(--color-state-danger) 15%, transparent);
    color: var(--color-state-danger);
    border-color: color-mix(in oklab, var(--color-state-danger) 35%, transparent);
  }
  .btn-danger:hover:not(:disabled) {
    background: color-mix(in oklab, var(--color-state-danger) 25%, transparent);
  }
</style>
