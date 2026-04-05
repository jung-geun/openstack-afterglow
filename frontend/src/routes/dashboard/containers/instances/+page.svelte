<script lang="ts">
  import { onMount } from 'svelte';
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
  }

  const statusColor: Record<string, string> = {
    Running:  'text-green-400 bg-green-900/30',
    Stopped:  'text-gray-400 bg-gray-800',
    Created:  'text-blue-400 bg-blue-900/30',
    Error:    'text-red-400 bg-red-900/30',
    Deleting: 'text-orange-400 bg-orange-900/30',
  };

  let containers = $state<ZunContainer[]>([]);
  let loading = $state(true);
  let error = $state('');
  let actionTarget = $state<string | null>(null);
  let showModal = $state(false);
  let creating = $state(false);
  let createError = $state('');
  let form = $state({ name: '', image: '', command: '', cpu: 0.5, memory: '512' });

  async function fetchContainers() {
    try {
      containers = await api.get<ZunContainer[]>('/api/containers', $auth.token ?? undefined, $auth.projectId ?? undefined);
      error = '';
    } catch (e) {
      error = e instanceof ApiError ? `조회 실패 (${e.status}): ${e.message}` : '서버 오류';
    } finally {
      loading = false;
    }
  }

  async function createContainer() {
    if (!form.name.trim() || !form.image.trim()) return;
    creating = true;
    createError = '';
    try {
      const body: Record<string, unknown> = {
        name: form.name,
        image: form.image,
        cpu: form.cpu,
        memory: form.memory,
      };
      if (form.command.trim()) body.command = form.command;
      await api.post('/api/containers', body, $auth.token ?? undefined, $auth.projectId ?? undefined);
      showModal = false;
      form = { name: '', image: '', command: '', cpu: 0.5, memory: '512' };
      await fetchContainers();
    } catch (e) {
      createError = e instanceof ApiError ? e.message : '생성 실패';
    } finally {
      creating = false;
    }
  }

  async function startContainer(uuid: string) {
    actionTarget = uuid;
    try {
      await api.post(`/api/containers/${uuid}/start`, {}, $auth.token ?? undefined, $auth.projectId ?? undefined);
      await fetchContainers();
    } catch (e) {
      alert('시작 실패: ' + (e instanceof ApiError ? e.message : String(e)));
    } finally {
      actionTarget = null;
    }
  }

  async function stopContainer(uuid: string) {
    actionTarget = uuid;
    try {
      await api.post(`/api/containers/${uuid}/stop`, {}, $auth.token ?? undefined, $auth.projectId ?? undefined);
      await fetchContainers();
    } catch (e) {
      alert('중지 실패: ' + (e instanceof ApiError ? e.message : String(e)));
    } finally {
      actionTarget = null;
    }
  }

  async function deleteContainer(uuid: string, name: string) {
    if (!confirm(`컨테이너 "${name}"을 삭제하시겠습니까?`)) return;
    actionTarget = uuid;
    try {
      await api.delete(`/api/containers/${uuid}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
      await fetchContainers();
    } catch (e) {
      alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
    } finally {
      actionTarget = null;
    }
  }

  onMount(fetchContainers);
</script>

{#if showModal}
  <div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onclick={() => { showModal = false; createError = ''; }} role="dialog" aria-modal="true" tabindex="-1" onkeydown={(e) => e.key === 'Escape' && (showModal = false)}>
    <div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()} role="document" onkeydown={(e) => e.stopPropagation()}>
      <h2 class="text-lg font-semibold text-white mb-5">컨테이너 생성</h2>
      <div class="space-y-4">
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름</label>
          <input bind:value={form.name} type="text" placeholder="my-container" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이미지</label>
          <input bind:value={form.image} type="text" placeholder="nginx:latest" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 font-mono" />
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">명령 (선택)</label>
          <input bind:value={form.command} type="text" placeholder="/bin/sh -c 'echo hello'" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 font-mono" />
        </div>
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">CPU</label>
            <input bind:value={form.cpu} type="number" step="0.1" min="0.1" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
          </div>
          <div>
            <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">메모리 (MB)</label>
            <input bind:value={form.memory} type="text" placeholder="512" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
          </div>
        </div>
      </div>
      {#if createError}<div class="mt-3 text-red-400 text-xs">{createError}</div>{/if}
      <div class="flex justify-end gap-3 mt-6">
        <button onclick={() => { showModal = false; createError = ''; }} class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">취소</button>
        <button onclick={createContainer} disabled={creating || !form.name || !form.image} class="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors">{creating ? '생성 중...' : '생성'}</button>
      </div>
    </div>
  </div>
{/if}

<div class="p-8">
  <div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold text-white">컨테이너</h1>
    <button onclick={() => showModal = true} class="bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">+ 컨테이너 생성</button>
  </div>

  {#if error}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>{/if}

  {#if loading}
    <LoadingSkeleton variant="table" rows={4} />
  {:else if containers.length === 0}
    <div class="text-center py-20 text-gray-600">
      <p class="text-lg mb-2">컨테이너가 없습니다</p>
      <p class="text-sm">Zun을 통해 새 컨테이너를 생성하세요</p>
    </div>
  {:else}
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
            <th class="text-left py-3 pr-6">이름</th>
            <th class="text-left py-3 pr-6">상태</th>
            <th class="text-left py-3 pr-6">이미지</th>
            <th class="text-left py-3 pr-6">CPU</th>
            <th class="text-left py-3 pr-6">메모리</th>
            <th class="text-left py-3 pr-6">생성일</th>
            <th class="text-left py-3"></th>
          </tr>
        </thead>
        <tbody>
          {#each containers as c (c.uuid)}
            <tr class="border-b border-gray-800/50 hover:bg-gray-800/50 transition-colors">
              <td class="py-3 pr-6">
                <button onclick={() => goto(`/dashboard/containers/instances/${c.uuid}`)} class="font-medium text-white hover:text-blue-400 transition-colors text-left">{c.name}</button>
              </td>
              <td class="py-3 pr-6">
                <span class="px-2 py-0.5 rounded text-xs font-medium {statusColor[c.status] ?? 'text-gray-400 bg-gray-800'}">{c.status}</span>
              </td>
              <td class="py-3 pr-6 text-gray-400 text-xs font-mono">{c.image ?? '-'}</td>
              <td class="py-3 pr-6 text-gray-400 text-xs">{c.cpu ?? '-'}</td>
              <td class="py-3 pr-6 text-gray-400 text-xs">{c.memory ?? '-'}</td>
              <td class="py-3 pr-6 text-gray-400 text-xs">{c.created_at?.slice(0, 10) ?? '-'}</td>
              <td class="py-3">
                <div class="flex items-center gap-2">
                  {#if c.status === 'Running'}
                    <button onclick={() => stopContainer(c.uuid)} disabled={actionTarget === c.uuid} class="text-xs text-orange-400 hover:text-orange-300 disabled:opacity-40 transition-colors">중지</button>
                  {:else if c.status === 'Stopped' || c.status === 'Created'}
                    <button onclick={() => startContainer(c.uuid)} disabled={actionTarget === c.uuid} class="text-xs text-green-400 hover:text-green-300 disabled:opacity-40 transition-colors">시작</button>
                  {/if}
                  <button onclick={() => deleteContainer(c.uuid, c.name)} disabled={actionTarget === c.uuid} class="text-xs text-red-400 hover:text-red-300 disabled:opacity-40 transition-colors">삭제</button>
                </div>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
