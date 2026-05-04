<script lang="ts">
  interface Props {
    label: string;
    used: number;
    limit: number;
    color?: string;
  }

  let { label, used, limit, color }: Props = $props();

  const pct = $derived(limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 0);
  // auto-pick tone if caller didn't specify a raw class
  const barTone = $derived(
    color
      ? null
      : pct >= 95 ? 'danger' : pct >= 80 ? 'warning' : 'accent'
  );
</script>

<div>
  <div class="flex justify-between text-xs text-gray-400 mb-1.5">
    <span>{label}</span>
    <span><span class="text-white font-medium">{used}</span> / {limit}</span>
  </div>
  <div class="h-1 bg-gray-800 rounded-full overflow-hidden">
    {#if barTone}
      <div class="bar bar-{barTone} h-full rounded-full transition-all" style="width:{pct}%"></div>
    {:else}
      <div class="{color} h-full rounded-full transition-all" style="width:{pct}%"></div>
    {/if}
  </div>
</div>

<style>
  .bar-accent  { background: var(--color-accent); }
  .bar-warning { background: var(--color-state-warning); }
  .bar-danger  { background: var(--color-state-danger); }
</style>
