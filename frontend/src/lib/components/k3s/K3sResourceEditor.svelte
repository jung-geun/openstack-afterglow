<script lang="ts">
  import { untrack } from 'svelte';

  interface Props {
    title: string;
    initialData?: Record<string, string>;
    onSave: (data: Record<string, string>) => Promise<void>;
    onClose: () => void;
    saving?: boolean;
  }

  let { title, initialData = {}, onSave, onClose, saving = false }: Props = $props();

  let entries = $state(
    untrack(() => Object.entries(initialData).map(([k, v]) => ({ k, v, id: Math.random() })))
  );
  let error = $state('');

  function addEntry() {
    entries = [...entries, { k: '', v: '', id: Math.random() }];
  }

  function removeEntry(id: number) {
    entries = entries.filter((e) => e.id !== id);
  }

  async function handleSave() {
    error = '';
    const data: Record<string, string> = {};
    for (const e of entries) {
      if (!e.k.trim()) continue;
      data[e.k.trim()] = e.v;
    }
    try {
      await onSave(data);
    } catch (err) {
      error = err instanceof Error ? err.message : '저장 실패';
    }
  }
</script>

<div
  class="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4"
  onclick={onClose}
  role="presentation"
>
  <div
    class="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-lg max-h-[80vh] overflow-hidden flex flex-col"
    onclick={(e) => e.stopPropagation()}
    role="presentation"
  >
    <div class="flex items-center justify-between px-4 py-3 border-b border-gray-800">
      <h3 class="text-sm font-medium text-gray-200">{title}</h3>
      <button onclick={onClose} class="text-gray-500 hover:text-gray-300 text-lg leading-none">&times;</button>
    </div>

    <div class="overflow-y-auto flex-1 p-4 space-y-2">
      {#each entries as entry (entry.id)}
        <div class="flex gap-2 items-start">
          <input
            bind:value={entry.k}
            placeholder="키"
            class="w-1/3 bg-gray-800 border border-gray-700 text-gray-200 text-xs rounded px-2 py-1.5 font-mono focus:outline-none focus:border-blue-500"
          />
          <textarea
            bind:value={entry.v}
            placeholder="값"
            rows="1"
            class="flex-1 bg-[#0f172a] border border-gray-700 text-gray-200 text-xs rounded px-2 py-1.5 font-mono focus:outline-none focus:border-blue-500 resize-y"
          ></textarea>
          <button
            onclick={() => removeEntry(entry.id)}
            class="text-gray-600 hover:text-red-400 text-xs px-1 py-1.5 shrink-0"
          >✕</button>
        </div>
      {/each}
      <button
        onclick={addEntry}
        class="text-xs text-blue-400 hover:text-blue-300 mt-1"
      >+ 항목 추가</button>
    </div>

    {#if error}
      <p class="text-xs text-red-400 px-4 pb-2">{error}</p>
    {/if}

    <div class="flex justify-end gap-2 px-4 py-3 border-t border-gray-800">
      <button onclick={onClose} class="text-xs text-gray-400 hover:text-gray-300 px-3 py-1.5">취소</button>
      <button
        onclick={handleSave}
        disabled={saving}
        class="text-xs text-blue-400 hover:text-blue-300 px-3 py-1.5 border border-blue-900 hover:border-blue-700 rounded transition-colors disabled:text-gray-600 disabled:border-gray-700"
      >
        {saving ? '저장 중...' : '저장'}
      </button>
    </div>
  </div>
</div>
