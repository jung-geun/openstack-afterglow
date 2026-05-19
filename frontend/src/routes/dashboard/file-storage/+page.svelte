<script lang="ts">
  import { auth } from '$lib/stores/auth';
  import { untrack } from 'svelte';
  import { api, ApiError } from '$lib/api/client';
  import { createSwr } from '$lib/utils/swr.svelte';
  import { apiMut } from '$lib/api/mutations';
  import type { FileStorage } from '$lib/types/resources';
  import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
  import SlidePanel from '$lib/components/SlidePanel.svelte';
  import FileStorageDetailPanel from '$lib/components/FileStorageDetailPanel.svelte';
  import PageHeader from '$lib/components/ui/PageHeader.svelte';
  import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
  import FileStorageWizard from '$lib/components/file-storage/wizard/FileStorageWizard.svelte';
  import FileStorageCard from '$lib/components/file-storage/FileStorageCard.svelte';

  interface QuotaItem { limit: number; in_use: number; }
  interface Quota { shares: QuotaItem; gigabytes: QuotaItem; share_networks: QuotaItem; }

  const token = $derived($auth.token ?? undefined);
  const projectId = $derived($auth.projectId ?? undefined);

  let fileStorages = $state<FileStorage[]>([]);
  let quota = $state<Quota | null>(null);
  let loading = $state(true);
  let refreshing = $state(false);
  let error = $state('');
  let deleting = $state<string | null>(null);
  let copiedExport = $state<string | null>(null);

  let selectedId = $state<string | null>(null);
  let showWizard = $state(false);

  function openDetailPanel(id: string) {
    selectedId = id;
    history.pushState({ fileStorageId: id }, '', `/dashboard/file-storage/${id}`);
  }

  function closeDetailPanel() {
    selectedId = null;
    history.pushState({}, '', '/dashboard/file-storage');
  }

  const { swrGet, swrSet } = createSwr(() => $auth.projectId);

  async function fetchFileStorages(opts?: { refresh?: boolean }) {
    const path = '/api/file-storage';
    const cached = swrGet<FileStorage[]>(path);
    if (cached && fileStorages.length === 0) fileStorages = cached;
    try {
      fileStorages = await api.get<FileStorage[]>(path, token, projectId, opts);
      swrSet(path, fileStorages);
      error = '';
    } catch (e) {
      if (!cached) error = e instanceof ApiError ? `조회 실패 (${e.status})` : '서버 오류';
    } finally {
      loading = false;
    }
  }

  async function fetchQuota() {
    try { quota = await api.get<Quota>('/api/file-storage/quota', token, projectId); }
    catch { quota = null; }
  }

  async function copyExportPath(path: string, id: string) {
    await navigator.clipboard.writeText(path);
    copiedExport = id;
    setTimeout(() => (copiedExport = null), 2000);
  }

  async function deleteFileStorage(id: string, name: string) {
    if (!confirm(`파일 스토리지 "${name || id.slice(0, 8)}"을 삭제하시겠습니까?`)) return;
    deleting = id;
    try {
      await apiMut('파일 스토리지 삭제', () => api.delete(`/api/file-storage/${id}`, token, projectId));
      await fetchFileStorages();
    } catch {
      // error toast shown by apiMut
    } finally { deleting = null; }
  }

  async function forceRefresh() {
    refreshing = true;
    try { await fetchFileStorages({ refresh: true }); }
    finally { refreshing = false; }
  }

  const ar = createAutoRefresh(() => { fetchFileStorages(); fetchQuota(); }, {
    storageKey: 'dashboard-file-storage-list',
    defaultActive: true,
    defaultInterval: 15,
    intervalOptions: [10, 15, 30, 60],
  });

  $effect(() => {
    const pid = $auth.projectId;
    if (!pid) return;
    untrack(() => { fetchFileStorages(); fetchQuota(); });
  });
</script>

<FileStorageWizard
  bind:open={showWizard}
  onCreated={() => fetchFileStorages()}
/>

<div class="p-4 md:p-8">
  <PageHeader breadcrumb="FILE STORAGE" title="파일 스토리지">
    {#snippet actions()}
      <AutoRefreshControl
        bind:active={ar.active}
        bind:intervalSeconds={ar.intervalSeconds}
        intervalOptions={ar.intervalOptions}
        refreshing={refreshing || loading}
        onManualRefresh={forceRefresh}
      />
      <button onclick={() => (showWizard = true)} class="bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">+ 파일 스토리지 생성</button>
    {/snippet}
  </PageHeader>

  {#if error}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>{/if}

  {#if loading}
    <div class="grid grid-cols-2 gap-3.5">
      {#each [1, 2, 3, 4] as _}
        <div class="animate-pulse bg-gray-900 border border-gray-800 rounded-2xl h-40"></div>
      {/each}
    </div>
  {:else if fileStorages.length === 0}
    <div class="text-center py-20 text-gray-600">
      <div class="text-5xl mb-4">🗂️</div>
      <p class="text-lg">파일 스토리지가 없습니다</p>
      <button onclick={() => (showWizard = true)} class="text-blue-400 hover:text-blue-300 text-sm mt-2 inline-block">첫 파일 스토리지를 생성하세요 →</button>
    </div>
  {:else}
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
      {#each fileStorages as fs (fs.id)}
        <FileStorageCard
          {fs}
          quotaLimit={quota?.gigabytes?.limit ?? 0}
          {copiedExport}
          {deleting}
          onOpenDetail={openDetailPanel}
          onCopyExport={copyExportPath}
          onDelete={deleteFileStorage}
        />
      {/each}
    </div>
  {/if}
</div>

{#if selectedId}
  <SlidePanel onClose={closeDetailPanel} width="w-full md:w-[60vw] max-w-2xl">
    <FileStorageDetailPanel
      fileStorageId={selectedId}
      onClose={closeDetailPanel}
      onDeleted={() => { fetchFileStorages(); closeDetailPanel(); }}
    />
  </SlidePanel>
{/if}
