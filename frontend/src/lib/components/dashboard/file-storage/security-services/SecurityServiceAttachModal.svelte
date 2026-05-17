<script lang="ts">
  import type { ShareNetwork } from '$lib/types/securityService';

  let {
    open = $bindable(),
    shareNetworks,
    attaching,
    error,
    selectedNetworkId = $bindable(),
    onAttach,
  }: {
    open: boolean;
    shareNetworks: ShareNetwork[];
    attaching: boolean;
    error: string;
    selectedNetworkId: string;
    onAttach: () => Promise<boolean>;
  } = $props();

  async function handleAttach() {
    const ok = await onAttach();
    if (ok) open = false;
  }
</script>

{#if open}
  <div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
    onclick={() => { open = false; }}
    role="dialog" aria-modal="true" tabindex="-1"
    onkeydown={(e) => e.key === 'Escape' && (open = false)}>
    <div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl"
      onclick={(e) => e.stopPropagation()} role="none" onkeydown={(e) => e.stopPropagation()}>
      <h2 class="text-lg font-semibold text-white mb-5">Share Network에 연결</h2>
      <div>
        <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">Share Network
          <select bind:value={selectedNetworkId}
            class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5">
            <option value="">Share Network 선택</option>
            {#each shareNetworks as net}
              <option value={net.id}>{net.name || net.id.slice(0, 12)}</option>
            {/each}
          </select>
        </label>
      </div>
      {#if error}
        <div class="mt-4 text-red-400 text-xs bg-red-900/20 border border-red-800 rounded px-3 py-2">{error}</div>
      {/if}
      <div class="flex justify-end gap-3 mt-6">
        <button onclick={() => { open = false; }}
          class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">취소</button>
        <button onclick={handleAttach} disabled={attaching || !selectedNetworkId}
          class="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors">
          {attaching ? '연결 중...' : '연결'}
        </button>
      </div>
    </div>
  </div>
{/if}
