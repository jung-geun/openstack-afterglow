<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props {
    breadcrumb: string;
    title: string;
    subtitle?: string;
    actions?: Snippet;
    class?: string;
  }

  let { breadcrumb, title, subtitle, actions, class: className = '' }: Props = $props();
</script>

<div class="flex items-start justify-between mb-6 {className}">
  <div>
    <div class="text-[11px] text-gray-500 uppercase tracking-widest font-medium mb-1">{breadcrumb}</div>
    <h1 class="text-[22px] font-bold text-white leading-tight">{title}</h1>
    {#if subtitle}
      <p class="text-[13px] text-gray-400 mt-0.5">{subtitle}</p>
    {/if}
  </div>
  {#if actions}
    <div class="flex items-center gap-2.5 shrink-0 ml-4 mt-0.5">
      {@render actions()}
    </div>
  {/if}
</div>
