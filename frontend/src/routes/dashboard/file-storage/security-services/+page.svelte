<script lang="ts">
	import { confirmDialog } from '$lib/stores/confirm.svelte';
  import { untrack } from 'svelte';
  import { auth } from '$lib/stores/auth';
  import { api, ApiError } from '$lib/api/client';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
  import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
  import PageHeader from '$lib/components/ui/PageHeader.svelte';
  import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
  import type { SecurityService, ShareNetwork } from '$lib/types/securityService';
  import SecurityServiceCreateModal from '$lib/components/dashboard/file-storage/security-services/SecurityServiceCreateModal.svelte';
  import SecurityServiceAttachModal from '$lib/components/dashboard/file-storage/security-services/SecurityServiceAttachModal.svelte';
  import SecurityServiceTable from '$lib/components/dashboard/file-storage/security-services/SecurityServiceTable.svelte';
  import { toast } from '$lib/stores/toast';

  let services = $state<SecurityService[]>([]);
  let shareNetworks = $state<ShareNetwork[]>([]);
  let loading = $state(true);
  let refreshing = $state(false);
  let deleting = $state<string | null>(null);
  let error = $state('');
  let showModal = $state(false);
  let showAttachModal = $state(false);
  let creating = $state(false);
  let attaching = $state(false);
  let createError = $state('');
  let attachError = $state('');
  let selectedServiceId = $state('');
  let selectedNetworkId = $state('');

  const token = $derived($auth.token ?? undefined);
  const projectId = $derived($auth.projectId ?? undefined);

  async function fetchServices(opts?: { refresh?: boolean }) {
    try {
      services = await api.get<SecurityService[]>('/api/v1/security-services', token, projectId, opts);
      error = '';
    } catch (e) {
      error = e instanceof ApiError ? `조회 실패 (${e.status})` : '서버 오류';
    } finally {
      loading = false;
    }
  }

  type CreateForm = { type: string; name: string; description: string; dns_ip: string; server: string; domain: string; user: string; password: string };

  async function createService(form: CreateForm): Promise<boolean> {
    if (!form.name.trim()) return false;
    creating = true; createError = '';
    try {
      await api.post('/api/v1/security-services', { ...form }, token, projectId);
      await fetchServices();
      return true;
    } catch (e) {
      createError = e instanceof ApiError ? e.message : '생성 실패';
      return false;
    } finally { creating = false; }
  }

  async function openAttachModal(serviceId: string) {
    selectedServiceId = serviceId; selectedNetworkId = ''; attachError = '';
    showAttachModal = true;
    try { shareNetworks = await api.get<ShareNetwork[]>('/api/v1/share-networks', token, projectId); }
    catch { shareNetworks = []; }
  }

  async function attachToNetwork(): Promise<boolean> {
    if (!selectedNetworkId) return false;
    attaching = true; attachError = '';
    try {
      await api.post(`/api/v1/security-services/${selectedServiceId}/attach?share_network_id=${selectedNetworkId}`, {}, token, projectId);
      toast.success('Share Network에 Security Service가 연결되었습니다.');
      return true;
    } catch (e) {
      attachError = e instanceof ApiError ? e.message : '연결 실패';
      return false;
    } finally { attaching = false; }
  }

  async function deleteService(id: string, name: string) {
    if (!await confirmDialog(`Security Service "${name}"을 삭제하시겠습니까?`)) return;
    deleting = id;
    try { await api.delete(`/api/v1/security-services/${id}`, token, projectId); await fetchServices(); }
    catch (e) { toast.error('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e))); }
    finally { deleting = null; }
  }

  async function forceRefresh() {
    refreshing = true;
    try { await fetchServices({ refresh: true }); } finally { refreshing = false; }
  }

  const ar = createAutoRefresh(() => fetchServices(), {
    storageKey: 'dashboard-file-storage-sec',
    defaultActive: true,
    defaultInterval: 60,
    intervalOptions: [10, 15, 30, 60],
  });

  $effect(() => {
    if (!$auth.projectId) return;
    loading = true;
    untrack(() => fetchServices());
  });
</script>

<SecurityServiceCreateModal bind:open={showModal} {creating} error={createError} onSubmit={createService} />
<SecurityServiceAttachModal bind:open={showAttachModal} {shareNetworks} {attaching} error={attachError} bind:selectedNetworkId onAttach={attachToNetwork} />

<div class="p-4 md:p-8">
  <PageHeader breadcrumb="FILE STORAGE / SECURITY SERVICES" title="Security Service">
    {#snippet actions()}
      <AutoRefreshControl bind:active={ar.active} bind:intervalSeconds={ar.intervalSeconds} intervalOptions={ar.intervalOptions} refreshing={refreshing || loading} onManualRefresh={forceRefresh} />
      <button onclick={() => { showModal = true; }}
        class="bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
        + Security Service 생성
      </button>
    {/snippet}
  </PageHeader>

  <p class="text-sm text-gray-500 mb-6">LDAP, Kerberos, Active Directory 인증 서비스를 Share Network에 연결하여 파일 스토리지 접근을 제어합니다.</p>

  {#if error}
    <div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>
  {/if}

  {#if loading}
    <LoadingSkeleton variant="table" rows={3} />
  {:else}
    <SecurityServiceTable {services} {deleting} onAttachClick={openAttachModal} onDelete={deleteService} onCreateClick={() => { showModal = true; }} />
  {/if}
</div>
