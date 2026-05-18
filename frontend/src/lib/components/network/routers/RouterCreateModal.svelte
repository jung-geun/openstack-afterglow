<script lang="ts">
  import type { Network } from '$lib/types/resources';

  let {
    open = $bindable(),
    externalNetworks,
    onCreate,
  }: {
    open: boolean;
    externalNetworks: Network[];
    onCreate: (form: { name: string; external_network_id: string }) => Promise<string | true>;
  } = $props();

  let form = $state({ name: '', external_network_id: '' });
  let creating = $state(false);
  let error = $state('');

  $effect(() => {
    if (!open) {
      form = { name: '', external_network_id: '' };
      error = '';
      creating = false;
    }
  });

  async function submit() {
    if (!form.name.trim()) return;
    creating = true;
    error = '';
    const result = await onCreate({ ...form });
    creating = false;
    if (result === true) open = false;
    else error = result;
  }
</script>

{#if open}
  <div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onclick={() => { open = false; }} role="dialog" aria-modal="true" tabindex="-1" onkeydown={(e) => e.key === 'Escape' && (open = false)}>
    <div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()} role="none" onkeydown={(e) => e.stopPropagation()}>
      <h2 class="text-lg font-semibold text-white mb-5">라우터 생성</h2>
      <div class="space-y-4">
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름
            <input bind:value={form.name} type="text" placeholder="my-router" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
          </label>
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">외부 네트워크 (선택)
            <select bind:value={form.external_network_id} class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5">
              <option value="">외부 게이트웨이 없음</option>
              {#each externalNetworks as net}
                <option value={net.id}>{net.name || net.id.slice(0, 12)}</option>
              {/each}
            </select>
          </label>
        </div>
      </div>
      {#if error}<div class="mt-4 text-red-400 text-xs bg-red-900/20 border border-red-800 rounded px-3 py-2">{error}</div>{/if}
      <div class="flex justify-end gap-3 mt-6">
        <button onclick={() => { open = false; }} class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">취소</button>
        <button onclick={submit} disabled={creating} class="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors">{creating ? '생성 중...' : '생성'}</button>
      </div>
    </div>
  </div>
{/if}
