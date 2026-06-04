<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props {
    title: string;
    meta?: string;
    right?: Snippet;
    class?: string;
  }

  let { title, meta, right, class: className = '' }: Props = $props();
</script>

<div class="flex items-center justify-between gap-2 {className}">
  <div class="flex items-baseline gap-2 min-w-0">
    <span class="text-[11px] uppercase tracking-wider font-medium text-gray-500 truncate">{title}</span>
    {#if meta}
      <span class="text-[11px] text-gray-600">{meta}</span>
    {/if}
  </div>
  {#if right}
    <div class="flex-shrink-0">
      {@render right()}
    </div>
  {/if}
</div>
