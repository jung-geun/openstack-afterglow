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

  const ACCENT_CLASSES: Record<string, string> = {
    blue:    'bg-blue-500/15 border-blue-500/30 text-blue-400',
    cyan:    'bg-cyan-500/15 border-cyan-500/30 text-cyan-400',
    violet:  'bg-violet-500/15 border-violet-500/30 text-violet-400',
    emerald: 'bg-emerald-500/15 border-emerald-500/30 text-emerald-400',
    amber:   'bg-amber-500/15 border-amber-500/30 text-amber-400',
    teal:    'bg-teal-500/15 border-teal-500/30 text-teal-400',
    rose:    'bg-rose-500/15 border-rose-500/30 text-rose-400',
    indigo:  'bg-indigo-500/15 border-indigo-500/30 text-indigo-400',
  };

  const chipClass = $derived(iconBgClass ?? (ACCENT_CLASSES[accent] ?? ACCENT_CLASSES.blue));

  const pct = $derived(
    progress && progress.max > 0
      ? Math.min(100, Math.round((progress.value / progress.max) * 100))
      : 0
  );
  const progressColor = $derived(
    pct > 80 ? 'bg-red-500' : pct > 60 ? 'bg-yellow-500' : 'bg-blue-500'
  );
</script>

<div class="bg-gray-900 border border-gray-800 rounded-2xl p-[18px] flex items-center gap-3.5 {className}">
  {#if icon}
    <div class="w-10 h-10 rounded-[10px] shrink-0 border flex items-center justify-center {chipClass}">
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
        <div class="h-1 rounded-full transition-all {progressColor}" style="width:{pct}%"></div>
      </div>
    {:else if footer}
      <div class="mt-1">
        {@render footer()}
      </div>
    {/if}
  </div>
</div>
