<script lang="ts">
  interface Props {
    label: string;
    used: number;
    limit: number;
    color?: string;
    size?: 'xs' | 'sm' | 'md';
    showValue?: boolean;
  }

  let { label, used, limit, color, size = 'xs', showValue = true }: Props = $props();

  const pct = $derived(limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 0);
  const barTone = $derived(
    color
      ? null
      : pct >= 95 ? 'danger' : pct >= 80 ? 'warning' : 'accent'
  );
  const trackH = $derived(size === 'md' ? 'h-2' : size === 'sm' ? 'h-1.5' : 'h-1');
</script>

<div>
  {#if showValue}
  <div class="flex justify-between text-xs text-gray-400 mb-1.5">
    <span>{label}</span>
    <span><span class="text-white font-medium">{used}</span> / {limit === -1 ? '무제한' : limit}</span>
  </div>
  {/if}
  <div class="{trackH} bg-gray-800 rounded-full overflow-hidden">
    {#if barTone}
      <div class="bar bar-{barTone} h-full rounded-full transition-all" style="width:{pct}%"></div>
    {:else}
      <div class="{color} h-full rounded-full transition-all" style="width:{pct}%"></div>
    {/if}
  </div>
</div>

<style>
  .bar-accent  { background: var(--gradient-usage); }
  .bar-warning { background: var(--gradient-usage-warning); }
  .bar-danger  { background: var(--gradient-usage-danger); }
</style>
