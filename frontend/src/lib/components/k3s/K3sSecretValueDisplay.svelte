<script lang="ts">
  interface Props {
    b64value: string;
  }

  let { b64value }: Props = $props();
  let revealed = $state(false);
  let copied = $state(false);

  const decoded = $derived.by(() => {
    try {
      return atob(b64value);
    } catch {
      return b64value;
    }
  });

  async function copy() {
    await navigator.clipboard.writeText(decoded);
    copied = true;
    setTimeout(() => { copied = false; }, 1500);
  }
</script>

<span class="inline-flex items-center gap-1.5 font-mono text-xs">
  {#if revealed}
    <span class="text-gray-200 break-all">{decoded}</span>
  {:else}
    <span class="text-gray-500">••••••••••</span>
  {/if}
  <button
    onclick={() => { revealed = !revealed; }}
    class="text-xs text-blue-500 hover:text-blue-400 shrink-0"
  >{revealed ? '숨기기' : 'Reveal'}</button>
  <button
    onclick={copy}
    class="text-xs text-gray-500 hover:text-gray-300 shrink-0"
    title="복사"
  >{copied ? '복사됨' : '복사'}</button>
</span>
