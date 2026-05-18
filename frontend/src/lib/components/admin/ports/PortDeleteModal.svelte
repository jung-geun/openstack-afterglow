<script lang="ts">
  import type { PortInfo } from '$lib/types/resources';

  let {
    port = $bindable<PortInfo | null>(),
    onConfirm,
  }: {
    port: PortInfo | null;
    onConfirm: (id: string) => Promise<string | true>;
  } = $props();

  let deleting = $state(false);
  let error = $state('');

  $effect(() => {
    if (port) {
      error = '';
      deleting = false;
    }
  });

  async function submit() {
    if (!port) return;
    deleting = true;
    error = '';
    const result = await onConfirm(port.id);
    deleting = false;
    if (result === true) {
      port = null;
    } else {
      error = result;
    }
  }
</script>

{#if port}
  <div
    class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
    onclick={() => { port = null; }}
    role="dialog"
    onkeydown={(e) => e.key === 'Escape' && (port = null)}
    tabindex="-1"
  >
    <div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-sm mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()}>
      <h2 class="text-lg font-semibold text-white mb-3">포트 삭제</h2>
      <p class="text-sm text-gray-400 mb-4">포트 <span class="text-white font-mono">{port.id.slice(0, 8)}...</span>을 삭제하시겠습니까?</p>
      {#if error}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>{/if}
      <div class="flex justify-end gap-3">
        <button onclick={() => { port = null; }} class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg">취소</button>
        <button onclick={submit} disabled={deleting} class="px-4 py-2 bg-red-600 hover:bg-red-500 text-white text-sm font-medium rounded-lg disabled:opacity-30">{deleting ? '삭제 중...' : '삭제'}</button>
      </div>
    </div>
  </div>
{/if}
