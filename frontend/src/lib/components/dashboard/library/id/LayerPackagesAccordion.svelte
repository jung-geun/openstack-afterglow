<script lang="ts">
  interface Props {
    packages: Record<string, unknown>;
  }

  let { packages }: Props = $props();

  let show = $state(false);
</script>

{#if Object.keys(packages).length > 0}
  <div class="bg-gray-800 rounded-lg border border-gray-700">
    <button
      class="w-full flex items-center justify-between px-5 py-3 text-sm font-medium"
      onclick={() => show = !show}
    >
      <span>설치된 패키지 ({Object.keys(packages).length})</span>
      <span class="text-gray-400">{show ? '▲' : '▼'}</span>
    </button>
    {#if show}
      <div class="px-5 pb-4 border-t border-gray-700">
        <pre class="text-xs text-gray-300 overflow-auto max-h-64 mt-3">{JSON.stringify(packages, null, 2)}</pre>
      </div>
    {/if}
  </div>
{/if}
