<script lang="ts">
  import { auth, isAdmin } from '$lib/stores/auth';
  import { api, ApiError } from '$lib/api/client';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
  import PageHeader from '$lib/components/ui/PageHeader.svelte';
  import TemplateCreateForm from '$lib/components/dashboard/library/templates/TemplateCreateForm.svelte';
  import TemplateTable from '$lib/components/dashboard/library/templates/TemplateTable.svelte';
  import TemplateDetailPanel from '$lib/components/dashboard/library/templates/TemplateDetailPanel.svelte';
  import type { TemplateInfo } from '$lib/types/templates';

  let templates = $state<TemplateInfo[]>([]);
  let loading = $state(true);
  let refreshing = $state(false);
  let error = $state('');
  let selectedTemplate = $state<TemplateInfo | null>(null);
  let panelOpen = $state(false);
  let loadingDetail = $state(false);
  let showCreateForm = $state(false);

  const token = $derived($auth.token ?? undefined);
  const projectId = $derived($auth.projectId ?? undefined);

  let initialLoaded = false;

  async function loadTemplates() {
    if (!initialLoaded) loading = true;
    else refreshing = true;
    error = '';
    try {
      templates = await api.get<TemplateInfo[]>('/api/union/templates', token, projectId);
      initialLoaded = true;
    } catch (e) {
      error = e instanceof ApiError ? e.message : '템플릿 로드 실패';
      templates = [];
    } finally {
      loading = false;
      refreshing = false;
    }
  }

  $effect(() => {
    if (token) loadTemplates();
  });

  async function openTemplate(t: TemplateInfo) {
    panelOpen = true;
    loadingDetail = true;
    try {
      const detail = await api.get<TemplateInfo>(
        `/api/union/templates/${encodeURIComponent(t.name)}/${t.version}`,
        token,
        projectId
      );
      selectedTemplate = detail;
    } catch {
      selectedTemplate = t;
    } finally {
      loadingDetail = false;
    }
  }

  async function handleCreateTemplate(form: {
    name: string;
    version: number;
    ubuntu_base: string;
    leaf_layer_id: string;
    note: string;
  }): Promise<boolean> {
    error = '';
    try {
      await api.post(
        '/api/union/templates',
        {
          name: form.name,
          version: form.version,
          ubuntu_base: form.ubuntu_base,
          leaf_layer_id: form.leaf_layer_id,
          note: form.note || null,
        },
        token,
        projectId
      );
      await loadTemplates();
      return true;
    } catch (e) {
      error = e instanceof ApiError ? e.message : '템플릿 생성 실패';
      return false;
    }
  }
</script>

<div class="flex flex-col h-full overflow-auto bg-gray-900 text-gray-100 p-6">
  <PageHeader title="템플릿" breadcrumb="라이브러리">
    {#snippet action()}
      <div class="flex items-center gap-2">
        {#if $isAdmin}
          <button
            onclick={() => { showCreateForm = !showCreateForm; }}
            class="px-3 py-1.5 text-sm bg-blue-600 hover:bg-blue-500 rounded-md transition-colors"
          >+ 새 템플릿</button>
        {/if}
        <button onclick={loadTemplates} class="text-xs text-gray-400 hover:text-white transition-colors px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600 flex items-center gap-1.5">새로고침</button>
      </div>
    {/snippet}
  </PageHeader>

  {#if error}
    <div class="mb-4 p-3 bg-red-900/40 border border-red-700 rounded-md text-red-300 text-sm">{error}</div>
  {/if}

  {#if showCreateForm && $isAdmin}
    <TemplateCreateForm
      bind:open={showCreateForm}
      {token}
      {projectId}
      onCreate={handleCreateTemplate}
    />
  {/if}

  {#if loading}
    <LoadingSkeleton rows={5} />
  {:else if templates.length === 0}
    <div class="flex flex-col items-center justify-center flex-1 text-gray-500">
      <p>등록된 템플릿이 없습니다</p>
    </div>
  {:else}
    <TemplateTable {templates} {refreshing} onSelect={openTemplate} />
  {/if}
</div>

{#if panelOpen}
  <TemplateDetailPanel
    template={selectedTemplate}
    loading={loadingDetail}
    onClose={() => { panelOpen = false; selectedTemplate = null; }}
  />
{/if}
