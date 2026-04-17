<script lang="ts">
  import { auth } from '$lib/stores/auth';
  import { api, ApiError } from '$lib/api/client';

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
    host: string | null;
  }

  interface Props {
    containerId: string;
    onClose?: () => void;
    adminMode?: boolean;
    onRefresh?: () => void;
  }

  let { containerId, onClose, adminMode = false, onRefresh }: Props = $props();

  const statusColor: Record<string, string> = {
    Running:  'text-green-400 bg-green-900/30',
    Stopped:  'text-gray-400 bg-gray-800',
    Created:  'text-blue-400 bg-blue-900/30',
    Error:    'text-red-400 bg-red-900/30',
    Deleting: 'text-orange-400 bg-orange-900/30',
  };

  const apiBase = $derived(adminMode ? '/api/admin/containers' : '/api/containers');

  const token = $derived($auth.token ?? undefined);
  const projectId = $derived($auth.projectId ?? undefined);

  let container = $state<ZunContainer | null>(null);
  let loading = $state(true);
  let error = $state('');
  let logs = $state('');
  let logsLoading = $state(false);
  let logsOpen = $state(false);
  let actioning = $state(false);
  let actionError = $state('');

  async function fetchContainer() {
    loading = true;
    error = '';
    try {
      container = await api.get<ZunContainer>(`${apiBase}/${containerId}`, token, projectId);
    } catch (e) {
      error = e instanceof ApiError ? `조회 실패: ${e.message}` : '서버 오류';
    } finally {
      loading = false;
    }
  }

  async function fetchLogs() {
    logsLoading = true;
    try {
      const res = await api.get<{ logs: string }>(`${apiBase}/${containerId}/logs`, token, projectId);
      logs = res.logs;
    } catch {
      logs = '로그를 가져올 수 없습니다';
    } finally {
      logsLoading = false;
    }
  }

  async function handleAction(action: 'start' | 'stop') {
    actioning = true;
    actionError = '';
    try {
      await api.post(`${apiBase}/${containerId}/${action}`, {}, token, projectId);
      await fetchContainer();
      onRefresh?.();
    } catch (e) {
      actionError = e instanceof ApiError ? e.message : `${action === 'start' ? '시작' : '중지'} 실패`;
    } finally {
      actioning = false;
    }
  }

  async function handleDelete() {
    if (!container) return;
    if (!confirm(`컨테이너 "${container.name}"을 삭제하시겠습니까?`)) return;
    actioning = true;
    actionError = '';
    try {
      await api.delete(`${apiBase}/${containerId}`, token, projectId);
      onRefresh?.();
      onClose?.();
    } catch (e) {
      actionError = e instanceof ApiError ? e.message : '삭제 실패';
      actioning = false;
    }
  }

  function toggleLogs() {
    logsOpen = !logsOpen;
    if (logsOpen && !logs) fetchLogs();
  }

  $effect(() => {
    if (containerId) fetchContainer();
  });
</script>

<div class="flex flex-col h-full">
  <!-- 헤더 -->
  <div class="flex items-center justify-between px-5 py-4 border-b border-gray-800 flex-shrink-0">
    <div>
      <h2 class="text-sm font-semibold text-white truncate">{container?.name ?? containerId.slice(0, 12)}</h2>
      <p class="text-xs text-gray-500 mt-0.5 font-mono">{containerId}</p>
    </div>
    <button onclick={onClose} class="text-gray-400 hover:text-white text-xl leading-none ml-3 flex-shrink-0" aria-label="닫기">×</button>
  </div>

  <div class="flex-1 overflow-y-auto p-5 space-y-4">
    {#if loading}
      <div class="text-gray-500 text-sm">로딩 중...</div>
    {:else if error}
      <div class="text-red-400 text-sm">{error}</div>
    {:else if container}
      <!-- 상태 & 액션 -->
      <div class="flex items-center justify-between">
        <span class="px-2 py-0.5 rounded text-xs font-medium {statusColor[container.status] ?? 'text-gray-400 bg-gray-800'}">
          {container.status}
        </span>
        <div class="flex items-center gap-2">
          {#if container.status === 'Running'}
            <button onclick={() => handleAction('stop')} disabled={actioning}
              class="px-3 py-1 text-xs text-orange-400 border border-orange-800 hover:bg-orange-900/30 rounded-lg transition-colors disabled:opacity-40">
              중지
            </button>
          {:else if container.status === 'Stopped' || container.status === 'Created'}
            <button onclick={() => handleAction('start')} disabled={actioning}
              class="px-3 py-1 text-xs text-green-400 border border-green-800 hover:bg-green-900/30 rounded-lg transition-colors disabled:opacity-40">
              시작
            </button>
          {/if}
          <button onclick={handleDelete} disabled={actioning}
            class="px-3 py-1 text-xs text-red-400 border border-red-800 hover:bg-red-900/30 rounded-lg transition-colors disabled:opacity-40">
            삭제
          </button>
        </div>
      </div>

      {#if actionError}
        <div class="text-red-400 text-xs">{actionError}</div>
      {/if}

      <!-- 기본 정보 -->
      <div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
        <h3 class="text-xs text-gray-500 uppercase tracking-wide mb-3">기본 정보</h3>
        <dl class="space-y-2 text-xs">
          <div class="flex justify-between gap-4">
            <dt class="text-gray-400 flex-shrink-0">이미지</dt>
            <dd class="text-gray-300 font-mono text-right break-all">{container.image ?? '-'}</dd>
          </div>
          {#if container.command}
            <div class="flex justify-between gap-4">
              <dt class="text-gray-400 flex-shrink-0">명령</dt>
              <dd class="text-gray-300 font-mono text-right break-all">{container.command}</dd>
            </div>
          {/if}
          <div class="flex justify-between">
            <dt class="text-gray-400">CPU</dt>
            <dd class="text-gray-300">{container.cpu ?? '-'}</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-gray-400">메모리</dt>
            <dd class="text-gray-300">{container.memory ? `${container.memory} MB` : '-'}</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-gray-400">호스트</dt>
            <dd class="text-gray-300 font-mono">{container.host ?? '-'}</dd>
          </div>
          <div class="flex justify-between">
            <dt class="text-gray-400">생성일</dt>
            <dd class="text-gray-300">{container.created_at?.slice(0, 19).replace('T', ' ') ?? '-'}</dd>
          </div>
          {#if container.status_reason}
            <div class="flex justify-between gap-4">
              <dt class="text-gray-400 flex-shrink-0">상태 메시지</dt>
              <dd class="text-gray-400 text-right break-all">{container.status_reason}</dd>
            </div>
          {/if}
        </dl>
      </div>

      <!-- 네트워크 -->
      {#if container.addresses && Object.keys(container.addresses).length > 0}
        <div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <h3 class="text-xs text-gray-500 uppercase tracking-wide mb-3">네트워크</h3>
          <div class="space-y-1.5 text-xs">
            {#each Object.entries(container.addresses) as [netName, addrs]}
              {#each addrs as a}
                <div class="flex justify-between">
                  <span class="text-gray-400">{netName}</span>
                  <span class="text-gray-300 font-mono">{a.addr}</span>
                </div>
              {/each}
            {/each}
          </div>
        </div>
      {/if}

      <!-- 로그 -->
      <div class="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <button
          onclick={toggleLogs}
          class="w-full flex items-center justify-between px-4 py-3 text-xs text-gray-400 hover:text-white transition-colors"
        >
          <span class="uppercase tracking-wide font-medium">로그</span>
          <span class="text-gray-600">{logsOpen ? '▲' : '▼'}</span>
        </button>
        {#if logsOpen}
          <div class="px-4 pb-4">
            <div class="flex justify-end mb-2">
              <button onclick={fetchLogs} disabled={logsLoading} class="text-xs text-blue-400 hover:text-blue-300 disabled:opacity-40">
                {logsLoading ? '조회 중...' : '새로고침'}
              </button>
            </div>
            {#if logs}
              <pre class="bg-gray-950 rounded p-3 text-xs text-gray-300 overflow-auto max-h-64 font-mono whitespace-pre-wrap">{logs}</pre>
            {:else}
              <div class="text-gray-600 text-xs">새로고침을 클릭하세요</div>
            {/if}
          </div>
        {/if}
      </div>
    {/if}
  </div>
</div>
