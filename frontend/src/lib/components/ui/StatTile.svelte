<script lang="ts">
  import type { Snippet } from 'svelte';

  type Accent = 'blue' | 'cyan' | 'violet' | 'emerald' | 'amber' | 'teal' | 'rose' | 'indigo';

  interface Props {
    label: string;
    value: string | number;
    unit?: string;
    delta?: string;
    icon?: Snippet;
    accent?: Accent;
    // legacy props
    suffix?: string;
    iconBgClass?: string;
    progress?: { value: number; max: number };
    footer?: Snippet;
    class?: string;
  }

  let {
    label,
    value,
    unit,
    suffix,
    delta,
    icon,
    accent = 'blue',
    iconBgClass,
    progress,
    footer,
    class: className = '',
  }: Props = $props();

  const displayUnit = $derived(unit ?? suffix);

  // Map legacy accent names to design-system tone classes
  const TONE_MAP: Record<Accent, string> = {
    blue:    'icon-accent',
    cyan:    'icon-info',
    violet:  'icon-accent2',
    emerald: 'icon-success',
    amber:   'icon-warning',
    teal:    'icon-info',
    rose:    'icon-danger',
    indigo:  'icon-accent2',
  };

  const chipClass = $derived(iconBgClass ?? TONE_MAP[accent] ?? TONE_MAP.blue);

  const pct = $derived(
    progress && progress.max > 0
      ? Math.min(100, Math.round((progress.value / progress.max) * 100))
      : 0
  );
  const progressTone = $derived(
    pct > 80 ? 'progress-danger' : pct > 60 ? 'progress-warning' : 'progress-accent'
  );
</script>

<div class="bg-gray-900 border border-gray-800 rounded-2xl p-[18px] flex items-center gap-3.5 {className}">
  {#if icon}
    <div class="icon-chip {chipClass}">
      {@render icon()}
    </div>
  {/if}
  <div class="flex-1 min-w-0">
    <div class="text-[11px] uppercase tracking-wider font-medium text-gray-500">{label}</div>
    <div class="flex items-baseline gap-2 mt-0.5 flex-wrap">
      <div class="text-[28px] font-bold text-white leading-none">{value}</div>
      {#if displayUnit}<div class="text-gray-500 text-xs">{displayUnit}</div>{/if}
      {#if delta}<div class="ml-auto text-emerald-400 text-[11px] font-medium">{delta}</div>{/if}
    </div>
    {#if progress && progress.max > 0}
      <div class="mt-2 w-full bg-gray-800 rounded-full h-1 overflow-hidden">
        <div class="progress-bar {progressTone} h-1 rounded-full transition-all" style="width:{pct}%"></div>
      </div>
    {:else if footer}
      <div class="mt-1">
        {@render footer()}
      </div>
    {/if}
  </div>
</div>

<style>
  .icon-chip {
    width: 40px;
    height: 40px;
    border-radius: 10px;
    border: 1px solid transparent;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .icon-accent {
    background: var(--accent-soft);
    border-color: var(--accent-ring);
    color: var(--color-accent);
  }
  .icon-accent2 {
    background: color-mix(in oklab, var(--color-accent-2) 14%, transparent);
    border-color: color-mix(in oklab, var(--color-accent-2) 30%, transparent);
    color: var(--color-accent-2);
  }
  .icon-success {
    background: color-mix(in oklab, var(--color-state-success) 14%, transparent);
    border-color: color-mix(in oklab, var(--color-state-success) 30%, transparent);
    color: var(--color-state-success);
  }
  .icon-warning {
    background: color-mix(in oklab, var(--color-state-warning) 14%, transparent);
    border-color: color-mix(in oklab, var(--color-state-warning) 30%, transparent);
    color: var(--color-state-warning);
  }
  .icon-danger {
    background: color-mix(in oklab, var(--color-state-danger) 14%, transparent);
    border-color: color-mix(in oklab, var(--color-state-danger) 30%, transparent);
    color: var(--color-state-danger);
  }
  .icon-info {
    background: color-mix(in oklab, var(--color-state-info) 14%, transparent);
    border-color: color-mix(in oklab, var(--color-state-info) 30%, transparent);
    color: var(--color-state-info);
  }

  .progress-accent  { background: var(--color-accent); }
  .progress-warning { background: var(--color-state-warning); }
  .progress-danger  { background: var(--color-state-danger); }
</style>
