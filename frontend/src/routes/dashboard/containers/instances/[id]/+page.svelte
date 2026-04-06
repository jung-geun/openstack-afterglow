<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
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

  // 콘솔 (exec) 상태
  let showConsole = $state(false);
  let terminalEl = $state<HTMLDivElement | null>(null);
  let terminalReady = $state(false);
  let consoleInput = $state('');
  let consoleOutput = $state('');
  let ws = $state<WebSocket | null>(null);
  let wsConnecting = $state(false);
  let wsConnected = $state(false);

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

  // xterm.js 터미널
  let terminal: import('@xterm/xterm').Terminal | null = null;
  let fitAddon: import('@xterm/addon-fit').FitAddon | null = null;

  async function openConsole() {
    showConsole = true;
    // DOM이 렌더된 후 터미널 초기화
    await new Promise(r => setTimeout(r, 100));
    if (!terminalEl) return;
    if (terminal) return; // already initialized

    const { Terminal } = await import('@xterm/xterm');
    const { FitAddon } = await import('@xterm/addon-fit');

    terminal = new Terminal({
      theme: { background: '#0f172a', foreground: '#e2e8f0', cursor: '#60a5fa' },
      fontFamily: 'monospace',
      fontSize: 13,
      cursorBlink: true,
    });
    fitAddon = new FitAddon();
    terminal.loadAddon(fitAddon);
    terminal.open(terminalEl);
    fitAddon.fit();
    terminalReady = true;

    connectWs();
  }

  function connectWs() {
    if (!terminal || wsConnecting) return;
    wsConnecting = true;

    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.hostname;
    const port = import.meta.env.PUBLIC_API_BASE ? new URL(import.meta.env.PUBLIC_API_BASE).port || '8000' : '8000';
    const url = `${proto}//${host}:${port}/api/containers/${containerId}/exec?token=${encodeURIComponent($auth.token ?? '')}&project_id=${encodeURIComponent($auth.projectId ?? '')}`;

    const socket = new WebSocket(url);
    ws = socket;

    socket.onopen = () => {
      wsConnecting = false;
      wsConnected = true;
    };

    socket.onmessage = (event) => {
      terminal?.write(event.data);
    };

    socket.onerror = () => {
      terminal?.write('\r\n\x1b[31m연결 오류가 발생했습니다\x1b[0m\r\n');
      wsConnected = false;
      wsConnecting = false;
    };

    socket.onclose = () => {
      wsConnected = false;
      wsConnecting = false;
      terminal?.write('\r\n\x1b[33m연결이 종료되었습니다\x1b[0m\r\n');
    };

    terminal!.onData((data) => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.send(data);
      }
    });
  }

  function closeConsole() {
    showConsole = false;
    ws?.close();
    ws = null;
    terminal?.dispose();
    terminal = null;
    fitAddon = null;
    terminalReady = false;
    wsConnected = false;
  }

  onMount(fetchContainer);

  onDestroy(() => {
    ws?.close();
    terminal?.dispose();
  });
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
          <button onclick={() => openConsole()} disabled={showConsole} class="px-4 py-2 text-sm text-blue-400 border border-blue-800 hover:bg-blue-900/30 rounded-lg transition-colors disabled:opacity-40">터미널</button>
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

    <!-- 인터랙티브 터미널 콘솔 -->
    {#if showConsole}
      <div class="bg-gray-900 border border-gray-700 rounded-xl mb-4 overflow-hidden">
        <div class="flex items-center justify-between px-4 py-2 bg-gray-800 border-b border-gray-700">
          <div class="flex items-center gap-2">
            <span class="text-sm text-white font-medium">터미널</span>
            {#if wsConnecting}
              <span class="text-xs text-yellow-400">연결 중...</span>
            {:else if wsConnected}
              <span class="text-xs text-green-400">● 연결됨</span>
            {:else}
              <span class="text-xs text-gray-500">● 연결 끊김</span>
            {/if}
          </div>
          <div class="flex gap-2">
            {#if !wsConnected && !wsConnecting}
              <button onclick={connectWs} class="text-xs text-blue-400 hover:text-blue-300 transition-colors">재연결</button>
            {/if}
            <button onclick={closeConsole} class="text-xs text-gray-400 hover:text-white transition-colors">✕ 닫기</button>
          </div>
        </div>
        <div bind:this={terminalEl} class="w-full" style="height: 320px; background: #0f172a;"></div>
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
