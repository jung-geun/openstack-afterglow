<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props {
    class?: string;
    children: Snippet;
  }

  let { class: className = '', children }: Props = $props();
</script>

<div class="text-[11px] uppercase tracking-wider font-medium text-gray-500 {className}">
  {@render children()}
</div>
