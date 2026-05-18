<script lang="ts">
  import { untrack } from 'svelte';
  import { auth } from '$lib/stores/auth';
  import { api, ApiError } from '$lib/api/client';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
  import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
  import PageHeader from '$lib/components/ui/PageHeader.svelte';
  import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
  import type { ZunContainer, ContainerListResponse, EnvVar, PortMapping } from '$lib/types/zunContainer';
  import ZunServiceBanner from '$lib/components/dashboard/containers/instances/ZunServiceBanner.svelte';
  import ContainersTable from '$lib/components/dashboard/containers/instances/ContainersTable.svelte';
  import ContainerCreateModal from '$lib/components/dashboard/containers/instances/ContainerCreateModal.svelte';

  let containers = $state<ZunContainer[]>([]);
  let serviceAvailable = $state(true);
  let serviceMessage = $state('');
  let loading = $state(true);
  let refreshing = $state(false);
  let error = $state('');
  let actionTarget = $state<string | null>(null);
  let showModal = $state(false);
  let creating = $state(false);
  let createError = $state('');

  async function fetchContainers(opts?: { refresh?: boolean }) {
    try {
      const resp = await api.get<ContainerListResponse>('/api/containers', $auth.token ?? undefined, $auth.projectId ?? undefined, opts);
      containers = resp.items;
      serviceAvailable = resp.service_available;
      serviceMessage = resp.message;
      error = '';
    } catch (e) {
      error = e instanceof ApiError ? `조회 실패 (${e.status}): ${e.message}` : '서버 오류';
    } finally {
      loading = false;
    }
  }

  async function forceRefresh() {
    refreshing = true;
    try {
      await fetchContainers({ refresh: true });
    } finally {
      refreshing = false;
    }
  }

  async function createContainer(payload: {
    name: string; image: string; command: string;
    cpu: number; memory: string;
    environment: EnvVar[]; ports: PortMapping[];
  }): Promise<boolean> {
    if (!payload.name.trim() || !payload.image.trim()) return false;
    creating = true;
    createError = '';
    try {
      const body: Record<string, unknown> = {
        name: payload.name,
        image: payload.image,
        cpu: payload.cpu,
        memory: payload.memory,
      };
      if (payload.command.trim()) body.command = payload.command;

      const envEntries = payload.environment.filter(e => e.key.trim());
      if (envEntries.length > 0) {
        const environment: Record<string, string> = {};
        envEntries.forEach(e => { environment[e.key.trim()] = e.value; });
        body.environment = environment;
      }

      const validPorts = payload.ports.filter(p => p.container_port > 0);
      if (validPorts.length > 0) {
        body.ports = validPorts.map(p => ({
          container_port: p.container_port,
          ...(p.host_port > 0 ? { host_port: p.host_port } : {}),
          protocol: p.protocol,
        }));
      }

      await api.post('/api/containers', body, $auth.token ?? undefined, $auth.projectId ?? undefined);
      showModal = false;
      await fetchContainers();
      return true;
    } catch (e) {
      createError = e instanceof ApiError ? e.message : '생성 실패';
      return false;
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

  const ar = createAutoRefresh(() => fetchContainers(), {
    storageKey: 'dashboard-zun-containers',
    defaultActive: true,
    defaultInterval: 10,
    intervalOptions: [10, 15, 30, 60],
  });

  $effect(() => {
    const projectId = $auth.projectId;
    if (!projectId) return;
    loading = true;
    untrack(() => fetchContainers());
  });

  $effect(() => {
    if (!showModal) createError = '';
  });
</script>

<ContainerCreateModal
  bind:open={showModal}
  {creating}
  error={createError}
  onCreate={createContainer}
/>

<div class="p-4 md:p-8">
  <PageHeader breadcrumb="CONTAINERS / INSTANCES" title="컨테이너">
    {#snippet actions()}
      <AutoRefreshControl
        bind:active={ar.active}
        bind:intervalSeconds={ar.intervalSeconds}
        intervalOptions={ar.intervalOptions}
        refreshing={refreshing || loading}
        onManualRefresh={forceRefresh}
      />
      <button onclick={() => showModal = true} class="bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">+ 컨테이너 생성</button>
    {/snippet}
  </PageHeader>

  {#if error}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>{/if}

  <ZunServiceBanner available={serviceAvailable} message={serviceMessage} />

  {#if loading}
    <LoadingSkeleton variant="table" rows={4} />
  {:else if !serviceAvailable}
    <div class="text-center py-20 text-gray-600">
      <p class="text-lg mb-2">Zun 서비스를 사용할 수 없습니다</p>
      <p class="text-sm">OpenStack 관리자에게 Zun 배포를 요청하세요</p>
    </div>
  {:else}
    <ContainersTable
      {containers}
      {actionTarget}
      onStart={startContainer}
      onStop={stopContainer}
      onDelete={deleteContainer}
    />
  {/if}
</div>
