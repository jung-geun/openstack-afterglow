<script lang="ts">
  import { untrack } from 'svelte';
  import { useK3sClusterDetailController } from '$lib/stores/k3sClusterDetailController.svelte';
  import K3sResourceEditor from './K3sResourceEditor.svelte';
  import { confirmDialog } from '$lib/stores/confirm.svelte';

  const s = useK3sClusterDetailController();

  let showCreate = $state(false);
  let newName = $state('');
  let editingCm = $state<{ name: string; data: Record<string, string> } | null>(null);
  let saving = $state(false);
  let createError = $state('');
  let loadError = $state('');

  $effect(() => {
    const ns = s.selectedNamespace;
    if (!ns) return;
    loadError = '';
    untrack(() => s.loadConfigMaps()).catch(() => { loadError = 'ConfigMap 로드 실패'; });
  });

  async function handleCreate(data: Record<string, string>) {
    if (!newName.trim()) { createError = '이름을 입력하세요'; return; }
    saving = true;
    createError = '';
    try {
      await s.saveConfigMap(newName.trim(), data, true);
      showCreate = false;
      newName = '';
    } catch (e) {
      createError = e instanceof Error ? e.message : '생성 실패';
    } finally {
      saving = false;
    }
  }

  async function handleEdit(data: Record<string, string>) {
    if (!editingCm) return;
    saving = true;
    try {
      await s.saveConfigMap(editingCm.name, data, false);
      editingCm = null;
    } finally {
      saving = false;
    }
  }

  async function handleDelete(name: string) {
    if (!(await confirmDialog(`ConfigMap "${name}"을 삭제하시겠습니까?`))) return;
    await s.deleteCm(name);
  }
</script>

<div class="bg-gray-900 border border-gray-800 rounded-xl p-4 mt-3">
  <div class="flex items-center justify-between mb-3">
    <h3 class="text-xs text-gray-500 uppercase tracking-wide">ConfigMaps</h3>
    <button
      onclick={() => { showCreate = !showCreate; newName = ''; createError = ''; }}
      class="text-xs text-blue-400 hover:text-blue-300 transition-colors"
    >{showCreate ? '닫기' : '+ 생성'}</button>
  </div>

  {#if showCreate}
    <div class="mb-3 bg-gray-800 rounded-lg p-3">
      <input
        bind:value={newName}
        placeholder="ConfigMap 이름"
        class="w-full bg-gray-700 border border-gray-600 text-gray-200 text-xs rounded px-2 py-1.5 font-mono mb-2 focus:outline-none focus:border-blue-500"
      />
      {#if createError}
        <p class="text-xs text-red-400 mb-1">{createError}</p>
      {/if}
      <p class="text-xs text-gray-500 mb-2">데이터를 추가하고 저장 버튼을 누르세요. 데이터 없이도 저장 가능합니다.</p>
      <K3sResourceEditor
        title="ConfigMap 생성"
        onSave={handleCreate}
        onClose={() => { showCreate = false; }}
        {saving}
      />
    </div>
  {/if}

  {#if loadError}
    <p class="text-xs text-red-400">{loadError}</p>
  {:else if s.configMaps.length === 0}
    <p class="text-xs text-gray-500">ConfigMap 없음</p>
  {:else}
    <div class="space-y-1.5">
      {#each s.configMaps as cm}
        {@const actionKey = `${s.selectedNamespace}:${cm.name}`}
        <div class="bg-gray-800/50 rounded-lg p-3 flex items-start justify-between gap-3">
          <div class="min-w-0 flex-1">
            <div class="text-xs text-gray-200 font-mono font-medium">{cm.name}</div>
            {#if Object.keys(cm.data).length > 0}
              <div class="flex flex-wrap gap-1 mt-1">
                {#each Object.keys(cm.data) as k}
                  <span class="text-xs bg-gray-700 text-gray-400 px-1.5 py-0.5 rounded font-mono">{k}</span>
                {/each}
              </div>
            {:else}
              <span class="text-xs text-gray-600 mt-0.5 block">데이터 없음</span>
            {/if}
          </div>
          <div class="flex gap-1 shrink-0">
            <button
              onclick={() => { editingCm = { name: cm.name, data: { ...cm.data } }; }}
              class="text-xs text-gray-400 hover:text-gray-200 px-2 py-1 border border-gray-700 hover:border-gray-500 rounded transition-colors"
            >편집</button>
            <button
              onclick={() => handleDelete(cm.name)}
              disabled={s.cmActioning === actionKey}
              class="text-xs text-orange-400 hover:text-orange-300 px-2 py-1 border border-orange-900 hover:border-orange-700 rounded transition-colors disabled:text-gray-600 disabled:border-gray-700 disabled:cursor-not-allowed"
            >{s.cmActioning === actionKey ? '삭제 중...' : '삭제'}</button>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

{#if editingCm}
  <K3sResourceEditor
    title={`ConfigMap 편집 — ${editingCm.name}`}
    initialData={editingCm.data}
    onSave={handleEdit}
    onClose={() => { editingCm = null; }}
    {saving}
  />
{/if}
