<script lang="ts">
  interface Props {
    label: string;
    used: number;
    limit: number;
    unit?: string;
  }

  let { label, used, limit, unit = '' }: Props = $props();

  const r = 28;
  const circumference = 2 * Math.PI * r;

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
  <div class="relative w-16 h-16">
    <svg viewBox="0 0 72 72" class="w-full h-full -rotate-90">
      <!-- Background track -->
      <circle
        cx="36" cy="36" r={r}
        fill="none"
        stroke="#374151"
        stroke-width="8"
      />
      <!-- Usage arc -->
      <circle
        cx="36" cy="36" r={r}
        fill="none"
        stroke={color}
        stroke-width="8"
        stroke-linecap="round"
        stroke-dasharray={circumference}
        stroke-dashoffset={dashOffset}
        class="transition-all duration-700"
      />
    </svg>
    <div class="absolute inset-0 flex items-center justify-center">
      <span class="text-xs font-bold" style="color: {color}">{limit > 0 ? `${pct}%` : '-'}</span>
    </div>
  </div>
  <div class="text-center">
    <div class="text-xs text-gray-300 font-medium leading-tight">{label}</div>
    <div class="text-xs text-gray-500 leading-tight">
      {#if limit > 0}
        {fmt(used)} / {fmt(limit)}
      {:else}
        {fmt(used)}
      {/if}
    </div>
  </div>
</div>
