<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { auth } from '$lib/stores/auth';
  import { api, ApiError } from '$lib/api/client';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';

  interface ZunContainer {
    uuid: string;
    name: string;
    status: string;
    status_reason: string | null;
    image: string | null;
    command: string | null;
    cpu: number | null;
    memory: string | null;
    created_at: string | null;
    addresses: Record<string, { addr: string }[]> | null;
  }

  const statusColor: Record<string, string> = {
    Running:  'text-green-400 bg-green-900/30',
    Stopped:  'text-gray-400 bg-gray-800',
    Created:  'text-blue-400 bg-blue-900/30',
    Error:    'text-red-400 bg-red-900/30',
    Deleting: 'text-orange-400 bg-orange-900/30',
  };

  let container = $state<ZunContainer | null>(null);
  let logs = $state('');
  let loading = $state(true);
  let logsLoading = $state(false);
  let error = $state('');
  let actioning = $state(false);

  const containerId = $derived($page.params.id);

  async function fetchContainer() {
    try {
      container = await api.get<ZunContainer>(`/api/containers/${containerId}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
      error = '';
    } catch (e) {
      error = e instanceof ApiError ? `조회 실패: ${e.message}` : '서버 오류';
    } finally {
      loading = false;
    }
  }

  async function fetchLogs() {
    logsLoading = true;
    try {
      const result = await api.get<{ logs: string }>(`/api/containers/${containerId}/logs`, $auth.token ?? undefined, $auth.projectId ?? undefined);
      logs = result.logs;
    } catch {
      logs = '로그를 가져올 수 없습니다';
    } finally {
      logsLoading = false;
    }
  }

  async function handleAction(action: 'start' | 'stop') {
    actioning = true;
    try {
      await api.post(`/api/containers/${containerId}/${action}`, {}, $auth.token ?? undefined, $auth.projectId ?? undefined);
      await fetchContainer();
    } catch (e) {
      alert(`${action === 'start' ? '시작' : '중지'} 실패: ` + (e instanceof ApiError ? e.message : String(e)));
    } finally {
      actioning = false;
    }
  }

  async function handleDelete() {
    if (!container) return;
    if (!confirm(`컨테이너 "${container.name}"을 삭제하시겠습니까?`)) return;
    try {
      await api.delete(`/api/containers/${containerId}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
      goto('/dashboard/containers/instances');
    } catch (e) {
      alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
    }
  }

  onMount(fetchContainer);
</script>

<div class="p-8 max-w-3xl">
  <div class="flex items-center gap-3 mb-6">
    <button onclick={() => goto('/dashboard/containers/instances')} class="text-gray-400 hover:text-white transition-colors">← 컨테이너 목록</button>
  </div>

  {#if error}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>{/if}

  {#if loading}
    <LoadingSkeleton variant="detail" />
  {:else if container}
    <div class="flex items-start justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-white">{container.name}</h1>
        <p class="text-gray-500 text-sm mt-1 font-mono">{container.uuid}</p>
      </div>
      <div class="flex gap-2">
        {#if container.status === 'Running'}
          <button onclick={() => handleAction('stop')} disabled={actioning} class="px-4 py-2 text-sm text-orange-400 border border-orange-800 hover:bg-orange-900/30 rounded-lg transition-colors disabled:opacity-40">중지</button>
        {:else if container.status === 'Stopped' || container.status === 'Created'}
          <button onclick={() => handleAction('start')} disabled={actioning} class="px-4 py-2 text-sm text-green-400 border border-green-800 hover:bg-green-900/30 rounded-lg transition-colors disabled:opacity-40">시작</button>
        {/if}
        <button onclick={handleDelete} class="px-4 py-2 text-sm text-red-400 border border-red-800 hover:bg-red-900/30 rounded-lg transition-colors">삭제</button>
      </div>
    </div>

    <div class="grid grid-cols-2 gap-4 mb-6">
      <div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
        <div class="text-xs text-gray-500 mb-1">상태</div>
        <span class="px-2 py-0.5 rounded text-xs font-medium {statusColor[container.status] ?? 'text-gray-400 bg-gray-800'}">{container.status}</span>
        {#if container.status_reason}
          <p class="text-xs text-gray-500 mt-2">{container.status_reason}</p>
        {/if}
      </div>
      <div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
        <div class="text-xs text-gray-500 mb-1">이미지</div>
        <div class="text-white text-xs font-mono">{container.image ?? '-'}</div>
      </div>
      <div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
        <div class="text-xs text-gray-500 mb-1">리소스</div>
        <div class="text-white text-sm">CPU {container.cpu ?? '-'} / MEM {container.memory ?? '-'} MB</div>
      </div>
      <div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
        <div class="text-xs text-gray-500 mb-1">생성일</div>
        <div class="text-white text-sm">{container.created_at?.slice(0, 19).replace('T', ' ') ?? '-'}</div>
      </div>
    </div>

    {#if container.command}
      <div class="bg-gray-900 border border-gray-800 rounded-xl p-4 mb-4">
        <div class="text-xs text-gray-500 mb-2">명령</div>
        <pre class="text-green-300 text-xs font-mono">{container.command}</pre>
      </div>
    {/if}

    <!-- 로그 섹션 -->
    <div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <div class="flex items-center justify-between mb-3">
        <div class="text-xs text-gray-500">로그</div>
        <button onclick={fetchLogs} disabled={logsLoading} class="text-xs text-blue-400 hover:text-blue-300 disabled:opacity-40 transition-colors">{logsLoading ? '조회 중...' : '새로고침'}</button>
      </div>
      {#if logs}
        <pre class="bg-gray-950 rounded p-3 text-xs text-gray-300 overflow-auto max-h-64 font-mono whitespace-pre-wrap">{logs}</pre>
      {:else}
        <div class="text-gray-600 text-xs">로그 새로고침 버튼을 클릭하세요</div>
      {/if}
    </div>
  {/if}
</div>
