<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props {
    class?: string;
    children: Snippet;
  }

  let { class: className = '', children }: Props = $props();
</script>

<div class="bg-gray-900 border border-gray-800 rounded-2xl {className}">
  {@render children()}
</div>
