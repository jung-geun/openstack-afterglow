<script lang="ts">
  let {
    open = $bindable(),
    creating,
    error,
    onCreate,
  }: {
    open: boolean;
    creating: boolean;
    error: string;
    onCreate: (body: Record<string, unknown>) => Promise<boolean>;
  } = $props();

  let form = $state({
    name: '',
    addSubnet: false,
    cidr: '10.0.0.0/24',
    gateway: '',
    dhcp: true,
  });

  function close() {
    open = false;
  }

  async function handleCreate() {
    if (!form.name.trim()) return;
    const body: Record<string, unknown> = { name: form.name };
    if (form.addSubnet) {
      body.subnet = {
        cidr: form.cidr,
        gateway_ip: form.gateway || null,
        enable_dhcp: form.dhcp,
      };
    }
    const ok = await onCreate(body);
    if (ok) {
      form = { name: '', addSubnet: false, cidr: '10.0.0.0/24', gateway: '', dhcp: true };
      open = false;
    }
  }
</script>

{#if open}
  <div
    class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
    onclick={close}
    role="dialog"
    aria-modal="true"
    tabindex="-1"
    onkeydown={(e) => e.key === 'Escape' && close()}
  >
    <div
      class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl"
      onclick={(e) => e.stopPropagation()}
      role="none"
      onkeydown={(e) => e.stopPropagation()}
    >
      <h2 class="text-lg font-semibold text-white mb-5">네트워크 생성</h2>
      <div class="space-y-4">
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름
            <input bind:value={form.name} type="text" placeholder="my-network" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
          </label>
        </div>
        <div class="flex items-center gap-2">
          <input type="checkbox" id="addSubnet" bind:checked={form.addSubnet} class="rounded border-gray-600" />
          <label for="addSubnet" class="text-sm text-gray-300">서브넷 함께 생성</label>
        </div>
        {#if form.addSubnet}
          <div>
            <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">CIDR
              <input bind:value={form.cidr} type="text" placeholder="10.0.0.0/24" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm font-mono focus:outline-none focus:border-blue-500 mt-1.5" />
            </label>
          </div>
          <div>
            <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">게이트웨이 (선택)
              <input bind:value={form.gateway} type="text" placeholder="10.0.0.1" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm font-mono focus:outline-none focus:border-blue-500 mt-1.5" />
            </label>
          </div>
          <div class="flex items-center gap-2">
            <input type="checkbox" id="dhcp" bind:checked={form.dhcp} class="rounded border-gray-600" />
            <label for="dhcp" class="text-sm text-gray-300">DHCP 활성화</label>
          </div>
        {/if}
      </div>
      {#if error}<div class="mt-4 text-red-400 text-xs bg-red-900/20 border border-red-800 rounded px-3 py-2">{error}</div>{/if}
      <div class="flex justify-end gap-3 mt-6">
        <button onclick={close} class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">취소</button>
        <button onclick={handleCreate} disabled={creating} class="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors">{creating ? '생성 중...' : '생성'}</button>
      </div>
    </div>
  </div>
{/if}
