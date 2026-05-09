<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props {
    class?: string;
    children: Snippet;
  }

  let { class: className = '', children }: Props = $props();
</script>

<div class="card bg-gray-900 border border-gray-800 rounded-2xl {className}">
  {@render children()}
</div>

<style>
  .card {
    position: relative;
    overflow: hidden;
  }
  .card::before {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    width: 60%;
    height: 60%;
    background: radial-gradient(ellipse at top left, color-mix(in oklab, var(--color-warm) 5%, transparent) 0%, transparent 70%);
    pointer-events: none;
    border-radius: inherit;
  }
</style>
