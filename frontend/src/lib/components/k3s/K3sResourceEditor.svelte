<script lang="ts">
  import {
    toConfigMapYaml,
    toSecretEditYaml,
    fromConfigMapEditYaml,
    fromSecretEditYaml,
  } from '$lib/utils/k8sYaml';

  interface Props {
    title: string;
    mode?: 'configmap' | 'secret';
    resourceName?: string;
    namespace?: string;
    secretType?: string;
    initialData?: Record<string, string>;
    onSave: (data: Record<string, string>) => Promise<void>;
    onClose: () => void;
    saving?: boolean;
  }

  let {
    title,
    mode = 'configmap',
    resourceName = '',
    namespace = '',
    secretType = 'Opaque',
    initialData = {},
    onSave,
    onClose,
    saving = false,
  }: Props = $props();

  function buildInitialYaml(): string {
    if (mode === 'secret') {
      return toSecretEditYaml(resourceName, secretType, namespace || undefined);
    }
    return toConfigMapYaml(resourceName, namespace, initialData);
  }

  let yamlText = $state(buildInitialYaml());
  let parseError = $state('');

  function validate(text: string): string {
    try {
      if (mode === 'secret') {
        fromSecretEditYaml(text);
      } else {
        fromConfigMapEditYaml(text);
      }
      return '';
    } catch (e) {
      return e instanceof Error ? e.message : String(e);
    }
  }

  let liveError = $derived(validate(yamlText));

  async function handleSave() {
    parseError = '';
    try {
      const data =
        mode === 'secret'
          ? fromSecretEditYaml(yamlText)
          : fromConfigMapEditYaml(yamlText);
      await onSave(data);
    } catch (e) {
      parseError = e instanceof Error ? e.message : '저장 실패';
    }
  }
</script>

<div
  class="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4"
  onclick={onClose}
  role="presentation"
>
  <div
    class="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-2xl max-h-[80vh] overflow-hidden flex flex-col"
    onclick={(e) => e.stopPropagation()}
    role="presentation"
  >
    <div class="flex items-center justify-between px-4 py-3 border-b border-gray-800">
      <h3 class="text-sm font-medium text-gray-200">{title}</h3>
      <button onclick={onClose} class="text-gray-500 hover:text-gray-300 text-lg leading-none">&times;</button>
    </div>

    <div class="overflow-y-auto flex-1 p-4">
      <textarea
        bind:value={yamlText}
        spellcheck={false}
        class="w-full h-72 bg-gray-950 border border-gray-700 text-gray-200 text-xs rounded-lg px-3 py-3 font-mono focus:outline-none focus:border-blue-500 resize-y leading-relaxed"
        placeholder={mode === 'secret'
          ? 'stringData:\n  KEY: value'
          : 'data:\n  KEY: value'}
      ></textarea>
      {#if liveError}
        <p class="text-xs text-red-400 mt-1">{liveError}</p>
      {/if}
    </div>

    {#if parseError}
      <p class="text-xs text-red-400 px-4 pb-2">{parseError}</p>
    {/if}

    <div class="flex justify-end gap-2 px-4 py-3 border-t border-gray-800">
      <button onclick={onClose} class="text-xs text-gray-400 hover:text-gray-300 px-3 py-1.5">취소</button>
      <button
        onclick={handleSave}
        disabled={saving || !!liveError}
        class="text-xs text-blue-400 hover:text-blue-300 px-3 py-1.5 border border-blue-900 hover:border-blue-700 rounded transition-colors disabled:text-gray-600 disabled:border-gray-700 disabled:cursor-not-allowed"
      >
        {saving ? '저장 중...' : '저장'}
      </button>
    </div>
  </div>
</div>
