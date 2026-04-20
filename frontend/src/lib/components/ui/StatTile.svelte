<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props {
    label: string;
    value: string | number;
    suffix?: string;
    icon?: Snippet;
    iconBgClass?: string;
    progress?: { value: number; max: number };
    footer?: Snippet;
    class?: string;
  }

  let {
    label,
    value,
    suffix,
    icon,
    iconBgClass = 'bg-blue-900/40',
    progress,
    footer,
    class: className = '',
  }: Props = $props();

  const pct = $derived(
    progress && progress.max > 0
      ? Math.min(100, Math.round((progress.value / progress.max) * 100))
      : 0
  );

  const progressColor = $derived(
    pct > 80 ? 'bg-red-500' : pct > 60 ? 'bg-yellow-500' : 'bg-blue-500'
  );
</script>

<div class="bg-gray-900 border border-gray-800 rounded-2xl p-5 flex flex-col min-h-[128px] {className}">
  <div class="flex items-center justify-between mb-3">
    <span class="text-[11px] text-gray-500 uppercase tracking-wider font-medium">{label}</span>
    {#if icon}
      <div class="w-8 h-8 rounded-full flex items-center justify-center {iconBgClass}">
        {@render icon()}
      </div>
    {/if}
  </div>

  <div class="text-3xl font-bold text-white leading-tight mb-1">
    {value}{#if suffix}<span class="text-lg text-gray-500 font-normal"> {suffix}</span>{/if}
  </div>

  {#if progress && progress.max > 0}
    <div class="mt-auto w-full bg-gray-800 rounded-full h-2 overflow-hidden">
      <div class="h-2 rounded-full transition-all {progressColor}" style="width:{pct}%"></div>
    </div>
  {:else if footer}
    <div class="mt-auto pt-2">
      {@render footer()}
    </div>
  {/if}
</div>
