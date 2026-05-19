<script lang="ts">
  import type { Service, NetworkAgent, EndpointGroup, StoragePool, TabKey } from '$lib/types/adminServices';
  import ServiceTable from './ServiceTable.svelte';
  import NetworkAgentTable from './NetworkAgentTable.svelte';
  import EndpointsTable from './EndpointsTable.svelte';
  import StoragePoolsList from './StoragePoolsList.svelte';
  import {
    COMPUTE_COLUMNS,
    BLOCK_STORAGE_COLUMNS,
    SHARED_FS_COLUMNS,
    ORCHESTRATION_COLUMNS,
    CONTAINER_COLUMNS,
    CONTAINER_INFRA_COLUMNS,
  } from './serviceColumns.js';

  let {
    activeTab,
    computeServices,
    blockStorageServices,
    networkAgents,
    sharedFsServices,
    orchestrationServices,
    containerServices,
    magnumServices,
    endpoints,
    storagePools,
    loadingMap,
  }: {
    activeTab: TabKey;
    computeServices: Service[];
    blockStorageServices: Service[];
    networkAgents: NetworkAgent[];
    sharedFsServices: Service[];
    orchestrationServices: Service[];
    containerServices: Service[];
    magnumServices: Service[];
    endpoints: EndpointGroup[];
    storagePools: StoragePool[];
    loadingMap: Record<TabKey, boolean>;
  } = $props();
</script>

{#if activeTab === 'compute'}
  <ServiceTable services={computeServices} columns={COMPUTE_COLUMNS} loading={loadingMap.compute} emptyMessage="데이터 없음" />
{:else if activeTab === 'network'}
  <NetworkAgentTable agents={networkAgents} loading={loadingMap.network} emptyMessage="데이터 없음" />
{:else if activeTab === 'block_storage'}
  <ServiceTable services={blockStorageServices} columns={BLOCK_STORAGE_COLUMNS} loading={loadingMap.block_storage} emptyMessage="데이터 없음" />
{:else if activeTab === 'shared_file_system'}
  <ServiceTable services={sharedFsServices} columns={SHARED_FS_COLUMNS} loading={loadingMap.shared_file_system} emptyMessage="Manila 서비스가 없거나 접근할 수 없습니다" />
{:else if activeTab === 'orchestration'}
  <ServiceTable services={orchestrationServices} columns={ORCHESTRATION_COLUMNS} loading={loadingMap.orchestration} emptyMessage="Heat 서비스가 없거나 접근할 수 없습니다" />
{:else if activeTab === 'container'}
  <ServiceTable services={containerServices} columns={CONTAINER_COLUMNS} loading={loadingMap.container} emptyMessage="Zun 서비스가 없거나 접근할 수 없습니다" />
{:else if activeTab === 'container_infra'}
  <ServiceTable services={magnumServices} columns={CONTAINER_INFRA_COLUMNS} loading={loadingMap.container_infra} emptyMessage="Magnum 서비스가 없거나 접근할 수 없습니다" />
{:else if activeTab === 'endpoints'}
  <EndpointsTable {endpoints} loading={loadingMap.endpoints} emptyMessage="엔드포인트 정보를 가져올 수 없습니다" />
{:else if activeTab === 'storage_pools'}
  <StoragePoolsList pools={storagePools} loading={loadingMap.storage_pools} emptyMessage="스토리지 풀 정보를 가져올 수 없습니다" />
{/if}
