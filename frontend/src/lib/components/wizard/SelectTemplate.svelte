<script lang="ts">
  import { auth } from '$lib/stores/auth';
  import { wizard } from '$lib/stores/wizard';
  import { api, ApiError } from '$lib/api/client';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
  import StatusChip from '$lib/components/ui/StatusChip.svelte';

  interface LayerInfo {
    id: string;
    name: string;
    version: string;
    sealed: boolean;
  }

  interface TemplateInfo {
    name: string;
    version: number;
    created_at: string;
    ubuntu_base: string;
    leaf_layer_id: string;
    note: string | null;
    resolved_stack: LayerInfo[] | null;
  }

  let templates = $state<TemplateInfo[]>([]);
  let loading = $state(true);
  let error = $state('');
  let selectedName = $state<string | null>($wizard.templateName);
  let selectedVersion = $state<number | null>($wizard.templateVersion);
  let expandedTemplate = $state<string | null>(null);

  const token = $derived($auth.token ?? undefined);
  const projectId = $derived($auth.projectId ?? undefined);

  $effect(() => {
    if (token) loadTemplates();
  });

  async function loadTemplates() {
    loading = true;
    error = '';
    try {
      const list = await api.get<TemplateInfo[]>('/api/v1/union/templates', token, projectId);
      // resolved_stack 포함 상세 정보 로드
      const details = await Promise.all(
        list.map(t =>
          api.get<TemplateInfo>(`/api/v1/union/templates/${encodeURIComponent(t.name)}/${t.version}`, token, projectId)
            .catch(() => t)
        )
      );
      templates = details;
    } catch (e) {
      error = e instanceof ApiError ? e.message : '템플릿 로드 실패';
    } finally {
      loading = false;
    }
  }

  function selectTemplate(t: TemplateInfo) {
    if (selectedName === t.name && selectedVersion === t.version) {
      // 선택 해제
      selectedName = null;
      selectedVersion = null;
    } else {
      selectedName = t.name;
      selectedVersion = t.version;
    }
    wizard.update(w => ({ ...w, templateName: selectedName, templateVersion: selectedVersion }));
  }

  function toggleExpand(key: string) {
    expandedTemplate = expandedTemplate === key ? null : key;
  }
</script>

<div class="space-y-3">
  {#if error}
    <div class="p-3 bg-red-900/40 border border-red-700 rounded-md text-red-300 text-sm">{error}</div>
  {/if}

  {#if loading}
    <LoadingSkeleton rows={3} />
  {:else if templates.length === 0}
    <div class="text-center py-8 text-gray-500">
      <p class="text-sm">등록된 템플릿이 없습니다</p>
      <p class="text-xs mt-1">관리자에게 템플릿 등록을 요청하세요</p>
    </div>
  {:else}
    {#each templates as t}
      {@const key = `${t.name}@${t.version}`}
      {@const isSelected = selectedName === t.name && selectedVersion === t.version}
      <div
        class="rounded-lg border transition-colors {isSelected ? 'border-blue-500 bg-blue-900/20' : 'border-gray-700 bg-gray-800 hover:border-gray-600'}"
      >
        <button
          class="w-full flex items-start gap-3 p-4 text-left"
          onclick={() => selectTemplate(t)}
        >
          <div class="mt-0.5 w-4 h-4 rounded-full border-2 flex-shrink-0 {isSelected ? 'border-blue-400 bg-blue-400' : 'border-gray-500'}"></div>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <span class="font-medium text-gray-100">{t.name}</span>
              <span class="text-xs text-gray-500">v{t.version}</span>
            </div>
            <p class="text-xs text-gray-400 mt-0.5">{t.ubuntu_base}</p>
            {#if t.note}
              <p class="text-xs text-gray-500 mt-1">{t.note}</p>
            {/if}
          </div>
          {#if t.resolved_stack}
            <button
              class="text-xs text-gray-500 hover:text-gray-300 ml-2"
              onclick={(e) => { e.stopPropagation(); toggleExpand(key); }}
            >{expandedTemplate === key ? '▲' : '▼'} {t.resolved_stack.length}개 레이어</button>
          {/if}
        </button>

        {#if expandedTemplate === key && t.resolved_stack}
          <div class="px-4 pb-4 pt-0 border-t border-gray-700">
            <div class="flex flex-wrap gap-2 mt-3">
              {#each t.resolved_stack as layer, i}
                <div class="flex items-center gap-1 px-2 py-1 bg-gray-700/50 rounded text-xs">
                  <span class="text-gray-500">{i + 1}.</span>
                  <span class="text-gray-300">{layer.name}</span>
                  <span class="text-gray-500">{layer.version}</span>
                  <StatusChip status={layer.sealed ? 'sealed' : 'draft'} />
                </div>
              {/each}
            </div>
          </div>
        {/if}
      </div>
    {/each}
  {/if}
</div>
