<script lang="ts">
  import { api, ApiError } from '$lib/api/client';
  import type { LayerInfo } from '$lib/types/templates';

  let {
    open = $bindable(),
    token,
    projectId,
    onCreate,
  }: {
    open: boolean;
    token: string | undefined;
    projectId: string | undefined;
    onCreate: (form: { name: string; version: number; ubuntu_base: string; leaf_layer_id: string; note: string }) => Promise<boolean>;
  } = $props();

  let sealedLayers = $state<LayerInfo[]>([]);
  let newName = $state('');
  let newVersion = $state(1);
  let newUbuntuBase = $state('');
  let newLeafLayerId = $state('');
  let newNote = $state('');
  let submitting = $state(false);

  function resetForm() {
    newName = '';
    newVersion = 1;
    newUbuntuBase = '';
    newLeafLayerId = '';
    newNote = '';
    submitting = false;
  }

  async function loadSealedLayers() {
    try {
      const all = await api.get<LayerInfo[]>('/api/union/layers?limit=200', token, projectId);
      sealedLayers = all.filter((l) => l.sealed);
    } catch {}
  }

  let prevOpen = open;
  $effect(() => {
    if (open !== prevOpen) {
      if (open) loadSealedLayers();
      else resetForm();
      prevOpen = open;
    }
  });

  async function handleSubmit(e: Event) {
    e.preventDefault();
    if (submitting) return;
    submitting = true;
    const success = await onCreate({
      name: newName.trim(),
      version: newVersion,
      ubuntu_base: newUbuntuBase.trim(),
      leaf_layer_id: newLeafLayerId,
      note: newNote.trim(),
    });
    submitting = false;
    if (success) {
      resetForm();
      open = false;
    }
  }
</script>

<div class="mb-6 bg-gray-800 rounded-lg border border-gray-700 p-5">
  <h3 class="text-sm font-medium mb-4">새 템플릿 생성</h3>
  <form onsubmit={handleSubmit} class="grid grid-cols-2 gap-4">
    <div>
      <label class="block text-xs text-gray-400 mb-1">이름 *</label>
      <input bind:value={newName} type="text" placeholder="예: ml-pytorch" required
        class="w-full px-3 py-2 text-sm bg-gray-700 border border-gray-600 rounded-md focus:outline-none focus:border-blue-500" />
    </div>
    <div>
      <label class="block text-xs text-gray-400 mb-1">버전 *</label>
      <input bind:value={newVersion} type="number" min="1" required
        class="w-full px-3 py-2 text-sm bg-gray-700 border border-gray-600 rounded-md focus:outline-none focus:border-blue-500" />
    </div>
    <div>
      <label class="block text-xs text-gray-400 mb-1">Ubuntu Base *</label>
      <input bind:value={newUbuntuBase} type="text" placeholder="ubuntu-24.04" required
        class="w-full px-3 py-2 text-sm bg-gray-700 border border-gray-600 rounded-md focus:outline-none focus:border-blue-500" />
    </div>
    <div>
      <label class="block text-xs text-gray-400 mb-1">Leaf 레이어 *</label>
      <select bind:value={newLeafLayerId} required
        class="w-full px-3 py-2 text-sm bg-gray-700 border border-gray-600 rounded-md focus:outline-none focus:border-blue-500">
        <option value="">레이어 선택...</option>
        {#each sealedLayers as l}
          <option value={l.id}>{l.name} ({l.version})</option>
        {/each}
      </select>
    </div>
    <div class="col-span-2">
      <label class="block text-xs text-gray-400 mb-1">설명 (선택)</label>
      <input bind:value={newNote} type="text" placeholder="템플릿 설명"
        class="w-full px-3 py-2 text-sm bg-gray-700 border border-gray-600 rounded-md focus:outline-none focus:border-blue-500" />
    </div>
    <div class="col-span-2 flex gap-2">
      <button type="submit" disabled={submitting}
        class="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-md">
        {submitting ? '생성 중...' : '생성'}
      </button>
      <button type="button" onclick={() => (open = false)}
        class="px-4 py-2 text-sm bg-gray-700 hover:bg-gray-600 rounded-md">취소</button>
    </div>
  </form>
</div>
