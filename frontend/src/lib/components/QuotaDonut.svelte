<script lang="ts">
  interface Props {
    label: string;
    used: number;
    limit: number;
    unit?: string;
    size?: 'sm' | 'lg';
  }

  let { label, used, limit, unit = '', size = 'sm' }: Props = $props();

  const r = $derived(size === 'lg' ? 44 : 28);
  const circumference = $derived(2 * Math.PI * r);

  const pct = $derived(limit > 0 ? Math.min(100, Math.round(used / limit * 100)) : 0);
  const dashOffset = $derived(circumference - (pct / 100) * circumference);
  const color = $derived(
    pct >= 100 ? '#ef4444'   // red-500 full
    : pct > 80 ? '#f97316'   // orange-500 danger
    : '#3b82f6'              // blue-500 normal
  );

  function fmt(v: number): string {
    if (v >= 1024 && unit === 'MB') return `${Math.round(v / 1024)}GB`;
    if (v >= 1024 && unit === 'GB') return `${Math.round(v / 1024)}TB`;
    return `${v}${unit}`;
  }
</script>

<div class="flex flex-col items-center gap-1">
  <div class="relative {size === 'lg' ? 'w-28 h-28' : 'w-16 h-16'}">
    <svg viewBox="0 0 {size === 'lg' ? '112 112' : '72 72'}" class="w-full h-full -rotate-90">
      <!-- Background track -->
      <circle
        cx={size === 'lg' ? 56 : 36} cy={size === 'lg' ? 56 : 36} r={r}
        fill="none"
        stroke="#374151"
        stroke-width={size === 'lg' ? 10 : 8}
      />
      <!-- Usage arc -->
      <circle
        cx={size === 'lg' ? 56 : 36} cy={size === 'lg' ? 56 : 36} r={r}
        fill="none"
        stroke={color}
        stroke-width={size === 'lg' ? 10 : 8}
        stroke-linecap="round"
        stroke-dasharray={circumference}
        stroke-dashoffset={dashOffset}
        class="transition-all duration-700"
      />
    </svg>
    <div class="absolute inset-0 flex items-center justify-center">
      <span class="{size === 'lg' ? 'text-base' : 'text-xs'} font-bold" style="color: {color}">{limit > 0 ? `${pct}%` : '-'}</span>
    </div>
  </div>
  <div class="text-center">
    <div class="{size === 'lg' ? 'text-sm' : 'text-xs'} text-gray-300 font-medium leading-tight">{label}</div>
    <div class="{size === 'lg' ? 'text-sm' : 'text-xs'} text-gray-500 leading-tight">
      {#if limit > 0}
        {fmt(used)} / {fmt(limit)}
      {:else}
        {fmt(used)}
      {/if}
    </div>
  </div>
</div>
