<script lang="ts">
  import { auth } from '$lib/stores/auth';
  import { untrack } from 'svelte';
  import { api, ApiError } from '$lib/api/client';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
  import RefreshButton from '$lib/components/RefreshButton.svelte';

  interface SecurityService {
    id: string;
    name: string;
    description: string;
    type: string;
    dns_ip: string | null;
    server: string | null;
    domain: string | null;
    status: string;
    created_at: string | null;
  }

  interface ShareNetwork {
    id: string;
    name: string;
  }

  const typeLabel: Record<string, string> = {
    ldap: 'LDAP',
    kerberos: 'Kerberos',
    active_directory: 'Active Directory',
  };

  const statusColor: Record<string, string> = {
    active:   'text-green-400 bg-green-900/30',
    error:    'text-red-400 bg-red-900/30',
    inactive: 'text-gray-400 bg-gray-800',
    new:      'text-blue-400 bg-blue-900/30',
  };

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
  let form = $state({
    type: 'ldap' as 'ldap' | 'kerberos' | 'active_directory',
    name: '',
    description: '',
    dns_ip: '',
    server: '',
    domain: '',
    user: '',
    password: '',
  });

  const token = $derived($auth.token ?? undefined);
  const projectId = $derived($auth.projectId ?? undefined);

  async function fetchServices(opts?: { refresh?: boolean }) {
    try {
      services = await api.get<SecurityService[]>('/api/security-services', token, projectId, opts);
      error = '';
    } catch (e) {
      error = e instanceof ApiError ? `조회 실패 (${e.status})` : '서버 오류';
    } finally {
      loading = false;
    }
  }

  function openCreateModal() {
    showModal = true;
    createError = '';
    form = { type: 'ldap', name: '', description: '', dns_ip: '', server: '', domain: '', user: '', password: '' };
  }

  async function createService() {
    if (!form.name.trim()) return;
    creating = true;
    createError = '';
    try {
      await api.post('/api/security-services', {
        type: form.type,
        name: form.name,
        description: form.description,
        dns_ip: form.dns_ip,
        server: form.server,
        domain: form.domain,
        user: form.user,
        password: form.password,
      }, token, projectId);
      showModal = false;
      await fetchServices();
    } catch (e) {
      createError = e instanceof ApiError ? e.message : '생성 실패';
    } finally {
      creating = false;
    }
  }

  async function openAttachModal(serviceId: string) {
    selectedServiceId = serviceId;
    selectedNetworkId = '';
    attachError = '';
    showAttachModal = true;
    try {
      shareNetworks = await api.get<ShareNetwork[]>('/api/share-networks', token, projectId);
    } catch {
      shareNetworks = [];
    }
  }

  async function attachToNetwork() {
    if (!selectedNetworkId) return;
    attaching = true;
    attachError = '';
    try {
      await api.post(
        `/api/security-services/${selectedServiceId}/attach?share_network_id=${selectedNetworkId}`,
        {}, token, projectId
      );
      showAttachModal = false;
      alert('Share Network에 Security Service가 연결되었습니다.');
    } catch (e) {
      attachError = e instanceof ApiError ? e.message : '연결 실패';
    } finally {
      attaching = false;
    }
  }

  async function deleteService(id: string, name: string) {
    if (!confirm(`Security Service "${name}"을 삭제하시겠습니까?`)) return;
    deleting = id;
    try {
      await api.delete(`/api/security-services/${id}`, token, projectId);
      await fetchServices();
    } catch (e) {
      alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
    } finally {
      deleting = null;
    }
  }

  async function forceRefresh() {
    refreshing = true;
    try {
      await fetchServices({ refresh: true });
    } finally {
      refreshing = false;
    }
  }

  $effect(() => {
    if (!$auth.projectId) return;
    loading = true;
    untrack(() => fetchServices());
  });
</script>

{#if showModal}
  <div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
    onclick={() => { showModal = false; createError = ''; }}
    role="dialog" aria-modal="true" tabindex="-1"
    onkeydown={(e) => e.key === 'Escape' && (showModal = false)}>
    <div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-lg mx-4 shadow-2xl max-h-[90vh] overflow-y-auto"
      onclick={(e) => e.stopPropagation()} role="none" onkeydown={(e) => e.stopPropagation()}>
      <h2 class="text-lg font-semibold text-white mb-5">Security Service 생성</h2>
      <div class="space-y-4">
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">유형 *
            <select bind:value={form.type}
              class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5">
              <option value="ldap">LDAP</option>
              <option value="kerberos">Kerberos</option>
              <option value="active_directory">Active Directory</option>
            </select>
          </label>
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름 *
            <input bind:value={form.name} type="text" placeholder="my-security-service"
              class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
          </label>
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">설명 (선택)
            <input bind:value={form.description} type="text" placeholder="설명"
              class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
          </label>
        </div>
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">DNS IP
              <input bind:value={form.dns_ip} type="text" placeholder="192.168.1.10"
                class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
            </label>
          </div>
          <div>
            <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">서버 주소
              <input bind:value={form.server} type="text" placeholder="ldap.example.com"
                class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
            </label>
          </div>
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">도메인 (선택)
            <input bind:value={form.domain} type="text" placeholder="example.com"
              class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
          </label>
        </div>
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">사용자 (선택)
              <input bind:value={form.user} type="text" placeholder="bind user"
                class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
            </label>
          </div>
          <div>
            <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">비밀번호 (선택)
              <input bind:value={form.password} type="password" placeholder="••••••"
                class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
            </label>
          </div>
        </div>
      </div>
      {#if createError}
        <div class="mt-4 text-red-400 text-xs bg-red-900/20 border border-red-800 rounded px-3 py-2">{createError}</div>
      {/if}
      <div class="flex justify-end gap-3 mt-6">
        <button onclick={() => { showModal = false; createError = ''; }}
          class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">취소</button>
        <button onclick={createService} disabled={creating || !form.name.trim()}
          class="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors">
          {creating ? '생성 중...' : '생성'}
        </button>
      </div>
    </div>
  </div>
{/if}

{#if showAttachModal}
  <div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
    onclick={() => { showAttachModal = false; attachError = ''; }}
    role="dialog" aria-modal="true" tabindex="-1"
    onkeydown={(e) => e.key === 'Escape' && (showAttachModal = false)}>
    <div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl"
      onclick={(e) => e.stopPropagation()} role="none" onkeydown={(e) => e.stopPropagation()}>
      <h2 class="text-lg font-semibold text-white mb-5">Share Network에 연결</h2>
      <div>
        <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">Share Network
          <select bind:value={selectedNetworkId}
            class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5">
            <option value="">Share Network 선택</option>
            {#each shareNetworks as net}
              <option value={net.id}>{net.name || net.id.slice(0, 12)}</option>
            {/each}
          </select>
        </label>
      </div>
      {#if attachError}
        <div class="mt-4 text-red-400 text-xs bg-red-900/20 border border-red-800 rounded px-3 py-2">{attachError}</div>
      {/if}
      <div class="flex justify-end gap-3 mt-6">
        <button onclick={() => { showAttachModal = false; attachError = ''; }}
          class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">취소</button>
        <button onclick={attachToNetwork} disabled={attaching || !selectedNetworkId}
          class="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors">
          {attaching ? '연결 중...' : '연결'}
        </button>
      </div>
    </div>
  </div>
{/if}

<div class="p-4 md:p-8">
  <div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold text-white">Security Service</h1>
    <div class="flex items-center gap-2">
      <RefreshButton {refreshing} onclick={forceRefresh} />
      <button onclick={openCreateModal}
        class="bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
        + Security Service 생성
      </button>
    </div>
  </div>

  <p class="text-sm text-gray-500 mb-6">LDAP, Kerberos, Active Directory 인증 서비스를 Share Network에 연결하여 파일 스토리지 접근을 제어합니다.</p>

  {#if error}
    <div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>
  {/if}

  {#if loading}
    <LoadingSkeleton variant="table" rows={3} />
  {:else if services.length === 0}
    <div class="text-center py-20 text-gray-600">
      <div class="text-5xl mb-4">🔐</div>
      <p class="text-lg">Security Service가 없습니다</p>
      <button onclick={openCreateModal} class="text-blue-400 hover:text-blue-300 text-sm mt-2 inline-block">
        Security Service를 생성하세요 →
      </button>
    </div>
  {:else}
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
            <th class="text-left py-3 pr-4">이름</th>
            <th class="text-left py-3 pr-4">유형</th>
            <th class="text-left py-3 pr-4">상태</th>
            <th class="text-left py-3 pr-4">DNS IP</th>
            <th class="text-left py-3 pr-4">서버</th>
            <th class="text-left py-3 pr-4">도메인</th>
            <th class="text-right py-3">액션</th>
          </tr>
        </thead>
        <tbody>
          {#each services as svc (svc.id)}
            <tr class="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
              <td class="py-3 pr-4 font-medium text-white">
                {svc.name}
                {#if svc.description}
                  <div class="text-xs text-gray-500">{svc.description}</div>
                {/if}
              </td>
              <td class="py-3 pr-4">
                <span class="px-2 py-0.5 rounded text-xs bg-purple-900/30 text-purple-300">
                  {typeLabel[svc.type] ?? svc.type}
                </span>
              </td>
              <td class="py-3 pr-4">
                <span class="px-2 py-0.5 rounded text-xs font-medium {statusColor[svc.status] ?? 'text-gray-400 bg-gray-800'}">
                  {svc.status || '-'}
                </span>
              </td>
              <td class="py-3 pr-4 text-xs text-gray-400 font-mono">{svc.dns_ip || '-'}</td>
              <td class="py-3 pr-4 text-xs text-gray-400">{svc.server || '-'}</td>
              <td class="py-3 pr-4 text-xs text-gray-400">{svc.domain || '-'}</td>
              <td class="py-3 text-right">
                <div class="flex justify-end gap-1">
                  <button onclick={() => openAttachModal(svc.id)}
                    class="text-blue-400 hover:text-blue-300 text-xs px-2 py-1 rounded border border-blue-900 hover:border-blue-700 transition-colors">
                    네트워크 연결
                  </button>
                  <button onclick={() => deleteService(svc.id, svc.name)}
                    disabled={deleting === svc.id}
                    class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-1 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors">
                    {deleting === svc.id ? '삭제 중...' : '삭제'}
                  </button>
                </div>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
