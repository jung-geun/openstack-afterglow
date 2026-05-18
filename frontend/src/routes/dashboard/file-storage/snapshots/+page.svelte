<script lang="ts">
  import { untrack } from 'svelte';
  import { auth } from '$lib/stores/auth';
  import { api, ApiError } from '$lib/api/client';
  import type { FileStorage, ShareSnapshot } from '$lib/types/resources';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
  import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
  import PageHeader from '$lib/components/ui/PageHeader.svelte';
  import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
  import SnapshotCreateModal from '$lib/components/file-storage/SnapshotCreateModal.svelte';
  import SnapshotListTable from '$lib/components/file-storage/SnapshotListTable.svelte';
  import SnapshotsEmptyState from '$lib/components/file-storage/SnapshotsEmptyState.svelte';

  let snapshots = $state<ShareSnapshot[]>([]);
  let fileStorages = $state<FileStorage[]>([]);
  let loading = $state(true);
  let refreshing = $state(false);
  let deleting = $state<string | null>(null);
  let error = $state('');
  let showModal = $state(false);

  const token = $derived($auth.token ?? undefined);
  const projectId = $derived($auth.projectId ?? undefined);

  async function fetchSnapshots(opts?: { refresh?: boolean }) {
    try {
      snapshots = await api.get<ShareSnapshot[]>('/api/share-snapshots', token, projectId, opts);
      error = '';
    } catch (e) {
      error = e instanceof ApiError ? `조회 실패 (${e.status})` : '서버 오류';
    } finally {
      loading = false;
    }
  }

  async function openCreateModal() {
    try {
      fileStorages = await api.get<FileStorage[]>('/api/file-storage', token, projectId);
    } catch {
      fileStorages = [];
    }
    showModal = true;
  }

  async function createSnapshot(form: { share_id: string; name: string; description: string }): Promise<string | true> {
    try {
      await api.post('/api/share-snapshots', {
        share_id: form.share_id,
        name: form.name,
        description: form.description || undefined,
      }, token, projectId);
      await fetchSnapshots();
      return true;
    } catch (e) {
      return e instanceof ApiError ? e.message : '생성 실패';
    }
  }

  async function deleteSnapshot(id: string, name: string) {
    if (!confirm(`스냅샷 "${name || id.slice(0, 8)}"을 삭제하시겠습니까?`)) return;
    deleting = id;
    try {
      await api.delete(`/api/share-snapshots/${id}`, token, projectId);
      await fetchSnapshots();
    } catch (e) {
      alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
    } finally {
      deleting = null;
    }
  }

  async function forceRefresh() {
    refreshing = true;
    try {
      await fetchSnapshots({ refresh: true });
    } finally {
      refreshing = false;
    }
  }

  const ar = createAutoRefresh(() => fetchSnapshots(), {
    storageKey: 'dashboard-file-storage-snapshots',
    defaultActive: true,
    defaultInterval: 15,
    intervalOptions: [10, 15, 30, 60],
  });

  $effect(() => {
    if (!$auth.projectId) return;
    loading = true;
    untrack(() => fetchSnapshots());
  });
</script>

<SnapshotCreateModal bind:open={showModal} {fileStorages} onCreate={createSnapshot} />

<div class="p-4 md:p-8">
  <PageHeader breadcrumb="FILE STORAGE / SNAPSHOTS" title="스냅샷">
    {#snippet actions()}
      <AutoRefreshControl
        bind:active={ar.active}
        bind:intervalSeconds={ar.intervalSeconds}
        intervalOptions={ar.intervalOptions}
        refreshing={refreshing || loading}
        onManualRefresh={forceRefresh}
      />
      <button onclick={openCreateModal} class="bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">+ 스냅샷 생성</button>
    {/snippet}
  </PageHeader>

  {#if error}
    <div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>
  {/if}

  {#if loading}
    <LoadingSkeleton variant="table" rows={4} />
  {:else if snapshots.length === 0}
    <SnapshotsEmptyState onCreate={openCreateModal} />
  {:else}
    <SnapshotListTable {snapshots} {deleting} onDelete={deleteSnapshot} />
  {/if}
</div>
