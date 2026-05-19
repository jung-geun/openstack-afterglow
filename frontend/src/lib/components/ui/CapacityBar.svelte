<script lang="ts">
  interface Props {
    label: string;
    used: number;
    total: number;
    unit?: string;
    size?: 'xs' | 'sm' | 'md';
    class?: string;
  }

  let { label, used, total, unit = '', size = 'sm', class: className = '' }: Props = $props();

  const pct = $derived(total > 0 ? Math.min(100, Math.round((used / total) * 100)) : 0);
  const tone = $derived(pct >= 95 ? 'danger' : pct >= 80 ? 'warning' : 'accent');
  const trackH = $derived(size === 'md' ? 'h-2' : size === 'sm' ? 'h-1.5' : 'h-1');

  const usedFmt = $derived(unit ? `${used}${unit}` : `${used}`);
  const totalFmt = $derived(unit ? `${total}${unit}` : `${total}`);
</script>

<div class={className}>
  <div class="flex items-baseline justify-between text-xs mb-1.5 gap-2">
    <span class="text-gray-400 truncate">{label}</span>
    <span class="text-gray-500 flex-shrink-0">
      <span class="text-white font-medium">{usedFmt}</span> / {totalFmt}
      <span class="ml-1 font-medium" class:text-danger={tone === 'danger'} class:text-warning={tone === 'warning'} class:text-gray-400={tone === 'accent'}>{pct}%</span>
    </span>
  </div>
  <div class="{trackH} bg-gray-800 rounded-full overflow-hidden">
    <div class="bar bar-{tone} h-full rounded-full transition-all" style="width:{pct}%"></div>
  </div>
</div>

<style>
  .bar-accent  { background: var(--gradient-usage); }
  .bar-warning { background: var(--gradient-usage-warning); }
  .bar-danger  { background: var(--gradient-usage-danger); }

  .text-warning { color: var(--color-state-warning); }
  .text-danger  { color: var(--color-state-danger); }
</style>
