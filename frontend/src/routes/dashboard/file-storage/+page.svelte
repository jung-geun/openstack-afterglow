<script lang="ts">
  import { auth } from '$lib/stores/auth';
  import { untrack } from 'svelte';
  import { api, ApiError, memoryCache } from '$lib/api/client';
  import type { FileStorage } from '$lib/types/resources';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
  import RefreshButton from '$lib/components/RefreshButton.svelte';
  import AutoRefreshToggle from '$lib/components/AutoRefreshToggle.svelte';
  import SlidePanel from '$lib/components/SlidePanel.svelte';
  import FileStorageDetailPanel from '$lib/components/FileStorageDetailPanel.svelte';

  // ────────── 공통 ──────────
  const token = $derived($auth.token ?? undefined);
  const projectId = $derived($auth.projectId ?? undefined);

  const statusColor: Record<string, string> = {
    available: 'text-green-400 bg-green-900/30',
    creating:  'text-yellow-400 bg-yellow-900/30',
    deleting:  'text-orange-400 bg-orange-900/30',
    error:     'text-red-400 bg-red-900/30',
  };

  interface QuotaItem { limit: number; in_use: number; }
  interface Quota { shares: QuotaItem; gigabytes: QuotaItem; share_networks: QuotaItem; }
  interface MetaEntry { key: string; value: string; }
  interface ShareNetwork { id: string; name: string; neutron_net_id: string | null; status: string; }
  interface NeutronNetwork { id: string; name: string; status: string; subnets: string[]; }
  interface Subnet { id: string; name: string; cidr: string; }
  interface AccessRule {
    id: string; access_type: string; access_to: string;
    access_level: string; access_key: string | null; state: string;
  }
  // ────────── 목록 ──────────
  let fileStorages = $state<FileStorage[]>([]);
  let quota = $state<Quota | null>(null);
  let loading = $state(true);
  let refreshing = $state(false);
  let error = $state('');
  let deleting = $state<string | null>(null);
  let autoRefresh = $state(false);
  let copiedExport = $state<string | null>(null);

  // ────────── 슬라이드 패널 ──────────
  let selectedId = $state<string | null>(null);

  function openDetailPanel(id: string) {
    selectedId = id;
    history.pushState({ fileStorageId: id }, '', `/dashboard/file-storage/${id}`);
  }

  function closeDetailPanel() {
    selectedId = null;
    history.pushState({}, '', '/dashboard/file-storage');
  }

  function swrGet<T>(path: string): T | null {
    const key = `${path}:${$auth.projectId}`;
    const c = memoryCache.get(key);
    return c ? (c.data as T) : null;
  }
  function swrSet(path: string, data: unknown) {
    memoryCache.set(`${path}:${$auth.projectId}`, { data, timestamp: Date.now() });
  }

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
      await api.delete(`/api/file-storage/${id}`, token, projectId);
      await fetchFileStorages();
    } catch (e) {
      alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
    } finally { deleting = null; }
  }

  async function forceRefresh() {
    refreshing = true;
    try { await fetchFileStorages({ refresh: true }); }
    finally { refreshing = false; }
  }

  $effect(() => {
    const pid = $auth.projectId;
    if (!pid) return;
    untrack(() => { fetchFileStorages(); fetchQuota(); });
  });

  $effect(() => {
    if (!$auth.projectId || !autoRefresh) return;
    const interval = setInterval(() => untrack(() => fetchFileStorages()), 10000);
    return () => clearInterval(interval);
  });

  // ────────── 위저드 ──────────
  type WizardStep = 1 | 2 | 3;
  let showWizard = $state(false);
  let wizardStep = $state<WizardStep>(1);
  let wizardError = $state('');
  let creating = $state(false);
  let createdFs = $state<FileStorage | null>(null);

  // Step 1: 기본 정보
  let shareTypes = $state<{ id: string; name: string; is_default: boolean }[]>([]);
  let fsForm = $state({ name: '', size_gb: 10, share_type: '', share_proto: 'CEPHFS' as 'CEPHFS' | 'NFS' });
  let metaEntries = $state<MetaEntry[]>([{ key: '', value: '' }]);

  // Step 2: 네트워크
  let shareNetworks = $state<ShareNetwork[]>([]);
  let selectedNetworkId = $state('');
  let showInlineNetCreate = $state(false);
  let neutronNetworks = $state<NeutronNetwork[]>([]);
  let subnets = $state<Subnet[]>([]);
  let loadingSubnets = $state(false);
  let inlineNetForm = $state({ name: '', description: '', neutron_net_id: '', neutron_subnet_id: '' });
  let inlineNetCreating = $state(false);
  let inlineNetError = $state('');

  // Step 3: 접근 규칙
  let accessRules = $state<AccessRule[]>([]);
  let ruleForm = $state({ access_to: '', access_level: 'rw' });
  let addingRule = $state(false);
  let ruleError = $state('');
  let copiedKey = $state<string | null>(null);

  function addMeta() { metaEntries = [...metaEntries, { key: '', value: '' }]; }
  function removeMeta(i: number) { metaEntries = metaEntries.filter((_, idx) => idx !== i); }

  async function openWizard() {
    showWizard = true; wizardStep = 1; wizardError = ''; createdFs = null;
    fsForm = { name: '', size_gb: 10, share_type: '', share_proto: 'CEPHFS' };
    metaEntries = [{ key: '', value: '' }];
    selectedNetworkId = ''; showInlineNetCreate = false;
    inlineNetForm = { name: '', description: '', neutron_net_id: '', neutron_subnet_id: '' };
    accessRules = []; ruleForm = { access_to: '', access_level: 'rw' };

    try {
      const [types, networks] = await Promise.all([
        api.get<{ id: string; name: string; is_default: boolean }[]>('/api/file-storage/types', token, projectId),
        api.get<ShareNetwork[]>('/api/share-networks', token, projectId),
      ]);
      shareTypes = types;
      shareNetworks = networks;
      if (shareTypes.length > 0) {
        fsForm.share_type = shareTypes.find(t => t.is_default)?.name ?? shareTypes[0].name;
      }
    } catch { shareTypes = []; shareNetworks = []; }
  }

  function closeWizard() {
    showWizard = false;
    if (createdFs) fetchFileStorages();
  }

  function goStep2() {
    if (!fsForm.name.trim() || fsForm.size_gb < 1) {
      wizardError = '이름과 크기를 입력하세요.'; return;
    }
    wizardError = '';
    wizardStep = 2;
    // Neutron 네트워크 미리 로드
    if (neutronNetworks.length === 0) {
      api.get<NeutronNetwork[]>('/api/networks', token, projectId)
        .then(r => neutronNetworks = r)
        .catch(() => neutronNetworks = []);
    }
  }

  async function onInlineNetworkChange() {
    inlineNetForm.neutron_subnet_id = ''; subnets = [];
    if (!inlineNetForm.neutron_net_id) return;
    loadingSubnets = true;
    try {
      const detail = await api.get<{ id: string; subnet_details: Subnet[] }>(`/api/networks/${inlineNetForm.neutron_net_id}`, token, projectId);
      subnets = detail.subnet_details ?? [];
    } catch { subnets = []; }
    finally { loadingSubnets = false; }
  }

  async function createInlineNetwork() {
    if (!inlineNetForm.name.trim() || !inlineNetForm.neutron_net_id || !inlineNetForm.neutron_subnet_id) return;
    inlineNetCreating = true; inlineNetError = '';
    try {
      const net = await api.post<ShareNetwork>('/api/share-networks', {
        name: inlineNetForm.name, description: inlineNetForm.description,
        neutron_net_id: inlineNetForm.neutron_net_id, neutron_subnet_id: inlineNetForm.neutron_subnet_id,
      }, token, projectId);
      shareNetworks = [...shareNetworks, net];
      selectedNetworkId = net.id;
      showInlineNetCreate = false;
      inlineNetForm = { name: '', description: '', neutron_net_id: '', neutron_subnet_id: '' };
    } catch (e) {
      inlineNetError = e instanceof ApiError ? e.message : '생성 실패';
    } finally { inlineNetCreating = false; }
  }

  async function createFileStorage() {
    if (fsForm.share_proto === 'NFS' && !selectedNetworkId) {
      wizardError = 'NFS 프로토콜은 Share Network가 필수입니다.'; return;
    }
    creating = true; wizardError = '';
    try {
      const body: Record<string, unknown> = {
        name: fsForm.name, size_gb: fsForm.size_gb,
        share_type: fsForm.share_type, share_proto: fsForm.share_proto,
      };
      if (selectedNetworkId) body.share_network_id = selectedNetworkId;
      const validMeta = metaEntries.filter(m => m.key.trim());
      if (validMeta.length > 0) {
        const metadata: Record<string, string> = {};
        validMeta.forEach(m => { metadata[m.key.trim()] = m.value; });
        body.metadata = metadata;
      }
      const created = await api.post<FileStorage>('/api/file-storage', body, token, projectId);
      createdFs = created;
      // 접근 규칙 목록 초기 조회
      try { accessRules = await api.get<AccessRule[]>(`/api/file-storage/${created.id}/access-rules`, token, projectId); }
      catch { accessRules = []; }
      wizardStep = 3;
    } catch (e) {
      wizardError = e instanceof ApiError ? e.message : '생성 실패';
    } finally { creating = false; }
  }

  async function addAccessRule() {
    if (!createdFs || !ruleForm.access_to.trim()) return;
    addingRule = true; ruleError = '';
    try {
      const access_type = createdFs.share_proto === 'NFS' ? 'ip' : 'cephx';
      const rule = await api.post<AccessRule>(
        `/api/file-storage/${createdFs.id}/access-rules`,
        { access_to: ruleForm.access_to.trim(), access_level: ruleForm.access_level, access_type },
        token, projectId
      );
      accessRules = [...accessRules, rule];
      ruleForm = { access_to: '', access_level: 'rw' };
    } catch (e) {
      ruleError = e instanceof ApiError ? e.message : '추가 실패';
    } finally { addingRule = false; }
  }

  async function copyKey(key: string, ruleId: string) {
    await navigator.clipboard.writeText(key);
    copiedKey = ruleId;
    setTimeout(() => (copiedKey = null), 2000);
  }
</script>

<!-- ===== 위저드 모달 ===== -->
{#if showWizard}
  <div
    class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
    onclick={closeWizard}
    role="dialog" aria-modal="true" tabindex="-1"
    onkeydown={(e) => e.key === 'Escape' && closeWizard()}
  >
    <div
      class="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-xl mx-4 shadow-2xl max-h-[90vh] overflow-y-auto"
      onclick={(e) => e.stopPropagation()}
      role="none" onkeydown={(e) => e.stopPropagation()}
    >
      <!-- 스텝 인디케이터 -->
      <div class="flex items-center gap-0 px-6 pt-6 pb-4 border-b border-gray-800">
        {#each [
          { step: 1, label: '기본 정보' },
          { step: 2, label: '네트워크' },
          { step: 3, label: '접근 설정' },
        ] as s}
          <div class="flex items-center {s.step < 3 ? 'flex-1' : ''}">
            <div class="flex flex-col items-center">
              <div class="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold border-2 transition-colors
                {wizardStep === s.step ? 'border-blue-500 bg-blue-900/40 text-blue-400' :
                 wizardStep > s.step ? 'border-green-600 bg-green-900/30 text-green-400' :
                 'border-gray-700 bg-gray-800 text-gray-500'}">
                {wizardStep > s.step ? '✓' : s.step}
              </div>
              <span class="text-xs mt-1 {wizardStep === s.step ? 'text-blue-400' : wizardStep > s.step ? 'text-green-400' : 'text-gray-600'}">{s.label}</span>
            </div>
            {#if s.step < 3}
              <div class="flex-1 h-px mx-3 mt-[-14px] {wizardStep > s.step ? 'bg-green-700' : 'bg-gray-700'}"></div>
            {/if}
          </div>
        {/each}
      </div>

      <div class="p-6">

        <!-- ===== STEP 1: 기본 정보 ===== -->
        {#if wizardStep === 1}
          <h2 class="text-base font-semibold text-white mb-4">파일 스토리지 기본 정보</h2>
          <div class="space-y-4">
            <div>
              <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름 *
                <input bind:value={fsForm.name} type="text" placeholder="my-file-storage"
                  class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
              </label>
            </div>
            <div>
              <span class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">크기 (GB)</span>
              <div class="flex gap-2 mb-2">
                {#each [10, 20, 50, 100] as preset}
                  <button type="button" onclick={() => fsForm.size_gb = preset}
                    class="flex-1 py-1.5 text-xs rounded-lg border transition-colors {fsForm.size_gb === preset ? 'border-blue-500 bg-blue-900/30 text-blue-400' : 'border-gray-600 text-gray-400 hover:border-gray-500'}">
                    {preset} GB
                  </button>
                {/each}
              </div>
              <input bind:value={fsForm.size_gb} type="number" min="1" placeholder="직접 입력"
                class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
            </div>
            <div>
              <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">Share Type
                {#if shareTypes.length > 0}
                  <select bind:value={fsForm.share_type} class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5">
                    {#each shareTypes as st}<option value={st.name}>{st.name}{st.is_default ? ' (기본값)' : ''}</option>{/each}
                  </select>
                {:else}
                  <input bind:value={fsForm.share_type} type="text" placeholder="share type 이름"
                    class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 font-mono mt-1.5" />
                {/if}
              </label>
            </div>
            <div>
              <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">프로토콜
                <select bind:value={fsForm.share_proto} class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5">
                  <option value="CEPHFS">CephFS</option>
                  <option value="NFS">NFS</option>
                </select>
              </label>
            </div>
            <div>
              <div class="flex items-center justify-between mb-2">
                <span class="block text-xs text-gray-400 uppercase tracking-wide">메타데이터 (선택)</span>
                <button type="button" onclick={addMeta} class="text-xs text-blue-400 hover:text-blue-300 transition-colors">+ 추가</button>
              </div>
              <div class="space-y-2">
                {#each metaEntries as meta, i (i)}
                  <div class="flex gap-2 items-center">
                    <input bind:value={meta.key} type="text" placeholder="key"
                      class="flex-1 bg-gray-800 border border-gray-600 rounded-lg px-3 py-1.5 text-white text-xs focus:outline-none focus:border-blue-500 font-mono" />
                    <span class="text-gray-600 text-xs">=</span>
                    <input bind:value={meta.value} type="text" placeholder="value"
                      class="flex-1 bg-gray-800 border border-gray-600 rounded-lg px-3 py-1.5 text-white text-xs focus:outline-none focus:border-blue-500 font-mono" />
                    <button type="button" onclick={() => removeMeta(i)} class="text-gray-600 hover:text-red-400 transition-colors text-xs px-1">✕</button>
                  </div>
                {/each}
              </div>
            </div>
          </div>
          {#if wizardError}<div class="mt-4 text-red-400 text-xs bg-red-900/20 border border-red-800 rounded px-3 py-2">{wizardError}</div>{/if}
          <div class="flex justify-end gap-3 mt-6">
            <button onclick={closeWizard} class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">취소</button>
            <button onclick={goStep2} class="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-colors">다음 →</button>
          </div>

        <!-- ===== STEP 2: 네트워크 설정 ===== -->
        {:else if wizardStep === 2}
          <h2 class="text-base font-semibold text-white mb-1">네트워크 설정</h2>
          <p class="text-xs text-gray-500 mb-4">
            {fsForm.share_proto === 'NFS' ? 'NFS 프로토콜은 Share Network 선택이 필수입니다.' : 'CephFS는 Share Network 없이도 기본값으로 동작합니다.'}
          </p>
          <div class="space-y-4">
            <!-- Share Network 선택 -->
            <div>
              <div class="flex items-center justify-between mb-1.5">
                <span class="text-xs text-gray-400 uppercase tracking-wide">Share Network {fsForm.share_proto === 'NFS' ? '*' : '(선택)'}</span>
                <button type="button" onclick={() => { showInlineNetCreate = !showInlineNetCreate; inlineNetError = ''; }}
                  class="text-xs text-blue-400 hover:text-blue-300 transition-colors">
                  {showInlineNetCreate ? '접기' : '+ 새로 생성'}
                </button>
              </div>
              {#if shareNetworks.length > 0}
                <select bind:value={selectedNetworkId} class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500">
                  <option value="">기본값 사용{fsForm.share_proto === 'NFS' ? '' : ' (권장)'}</option>
                  {#each shareNetworks as net}<option value={net.id}>{net.name || net.id.slice(0, 8)}{net.status ? ` (${net.status})` : ''}</option>{/each}
                </select>
              {:else if !showInlineNetCreate}
                <div class="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-500 text-sm">
                  Share Network 없음 —
                  <button onclick={() => showInlineNetCreate = true} class="text-blue-400 hover:text-blue-300 underline">지금 생성</button>
                </div>
              {/if}
            </div>

            <!-- 인라인 Share Network 생성 폼 -->
            {#if showInlineNetCreate}
              <div class="border border-gray-700 rounded-lg p-4 bg-gray-800/40 space-y-3">
                <p class="text-xs text-gray-400 font-medium uppercase tracking-wide">새 Share Network 생성</p>
                <div>
                  <label class="block text-xs text-gray-500 mb-1">이름 *
                    <input bind:value={inlineNetForm.name} type="text" placeholder="my-share-network"
                      class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1" />
                  </label>
                </div>
                <div>
                  <label class="block text-xs text-gray-500 mb-1">설명 (선택)
                    <input bind:value={inlineNetForm.description} type="text" placeholder="설명"
                      class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1" />
                  </label>
                </div>
                <div>
                  <label class="block text-xs text-gray-500 mb-1">Neutron 네트워크 *
                    <select bind:value={inlineNetForm.neutron_net_id} onchange={onInlineNetworkChange}
                      class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1">
                      <option value="">네트워크 선택</option>
                      {#each neutronNetworks as net}<option value={net.id}>{net.name || net.id.slice(0, 12)} ({net.status})</option>{/each}
                    </select>
                  </label>
                </div>
                <div>
                  <label class="block text-xs text-gray-500 mb-1">서브넷 *
                    {#if loadingSubnets}
                      <div class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-gray-500 text-sm mt-1">로딩 중...</div>
                    {:else}
                      <select bind:value={inlineNetForm.neutron_subnet_id} disabled={subnets.length === 0}
                        class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1 disabled:text-gray-600">
                        <option value="">{subnets.length === 0 ? '네트워크를 먼저 선택하세요' : '서브넷 선택'}</option>
                        {#each subnets as subnet}<option value={subnet.id}>{subnet.name || subnet.id.slice(0, 12)} {subnet.cidr ? `(${subnet.cidr})` : ''}</option>{/each}
                      </select>
                    {/if}
                  </label>
                </div>
                {#if inlineNetError}<div class="text-red-400 text-xs bg-red-900/20 border border-red-800 rounded px-3 py-2">{inlineNetError}</div>{/if}
                <div class="flex justify-end gap-2">
                  <button onclick={() => { showInlineNetCreate = false; inlineNetError = ''; }} class="px-3 py-1.5 text-xs text-gray-400 hover:text-white transition-colors">취소</button>
                  <button onclick={createInlineNetwork} disabled={inlineNetCreating || !inlineNetForm.name.trim() || !inlineNetForm.neutron_net_id || !inlineNetForm.neutron_subnet_id}
                    class="px-4 py-1.5 bg-blue-700 hover:bg-blue-600 disabled:bg-gray-700 disabled:text-gray-500 text-white text-xs font-medium rounded-lg transition-colors">
                    {inlineNetCreating ? '생성 중...' : 'Share Network 생성'}
                  </button>
                </div>
              </div>
            {/if}
          </div>

          {#if wizardError}<div class="mt-4 text-red-400 text-xs bg-red-900/20 border border-red-800 rounded px-3 py-2">{wizardError}</div>{/if}
          <div class="flex justify-between gap-3 mt-6">
            <button onclick={() => { wizardStep = 1; wizardError = ''; }} class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">← 이전</button>
            <div class="flex gap-3">
              <button onclick={closeWizard} class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">취소</button>
              <button onclick={createFileStorage} disabled={creating}
                class="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors">
                {creating ? '생성 중...' : '생성'}
              </button>
            </div>
          </div>

        <!-- ===== STEP 3: 접근 규칙 설정 ===== -->
        {:else if wizardStep === 3 && createdFs}
          <div class="flex items-center gap-2 mb-4">
            <span class="w-5 h-5 rounded-full bg-green-900/50 border border-green-600 flex items-center justify-center text-green-400 text-xs">✓</span>
            <h2 class="text-base font-semibold text-white">"{createdFs.name}" 생성 완료</h2>
          </div>

          <!-- Export Location -->
          {#if createdFs.export_locations && createdFs.export_locations.length > 0}
            <div class="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 mb-4">
              <p class="text-xs text-gray-500 mb-1">Export Location (마운트 경로)</p>
              <div class="flex items-center gap-2">
                <code class="text-xs text-green-300 font-mono flex-1 truncate">{createdFs.export_locations[0]}</code>
                <button onclick={() => copyExportPath(createdFs!.export_locations[0], createdFs!.id)}
                  class="shrink-0 text-gray-500 hover:text-gray-300 text-xs px-2 py-1 rounded border border-gray-700 transition-colors">
                  {copiedExport === createdFs.id ? '복사됨' : '복사'}
                </button>
              </div>
            </div>
          {/if}

          <!-- 접근 규칙 추가 -->
          <div class="mb-4">
            <p class="text-xs text-gray-400 uppercase tracking-wide mb-3">접근 규칙 추가</p>
            <div class="flex gap-2 items-end">
              <div class="flex-1">
                <label class="block text-xs text-gray-500 mb-1">
                  {createdFs.share_proto === 'NFS' ? 'IP / CIDR' : 'CephX ID'}
                  <input bind:value={ruleForm.access_to} type="text"
                    placeholder={createdFs.share_proto === 'NFS' ? '예: 192.168.1.0/24' : '예: my-client'}
                    class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1 font-mono" />
                </label>
              </div>
              <div>
                <label class="block text-xs text-gray-500 mb-1">권한
                  <select bind:value={ruleForm.access_level}
                    class="bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1">
                    <option value="rw">읽기/쓰기</option>
                    <option value="ro">읽기 전용</option>
                  </select>
                </label>
              </div>
              <button onclick={addAccessRule} disabled={addingRule || !ruleForm.access_to.trim()}
                class="px-4 py-2 bg-blue-700 hover:bg-blue-600 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm rounded-lg transition-colors whitespace-nowrap mb-[1px]">
                {addingRule ? '추가 중...' : '+ 추가'}
              </button>
            </div>
            {#if ruleError}<div class="mt-2 text-red-400 text-xs bg-red-900/20 border border-red-800 rounded px-3 py-2">{ruleError}</div>{/if}
          </div>

          <!-- 추가된 규칙 목록 -->
          {#if accessRules.length > 0}
            <div class="border border-gray-700 rounded-lg overflow-hidden mb-4">
              <table class="w-full text-xs">
                <thead>
                  <tr class="border-b border-gray-700 text-gray-500 uppercase tracking-wide bg-gray-800/50">
                    <th class="text-left px-3 py-2">{createdFs.share_proto === 'NFS' ? 'IP/CIDR' : 'CephX ID'}</th>
                    <th class="text-left px-3 py-2">권한</th>
                    <th class="text-left px-3 py-2">상태</th>
                    {#if createdFs.share_proto !== 'NFS'}<th class="text-left px-3 py-2">Access Key</th>{/if}
                  </tr>
                </thead>
                <tbody>
                  {#each accessRules as rule (rule.id)}
                    <tr class="border-b border-gray-800 last:border-0">
                      <td class="px-3 py-2 font-mono text-gray-300">{rule.access_to}</td>
                      <td class="px-3 py-2">
                        <span class="px-1.5 py-0.5 rounded {rule.access_level === 'rw' ? 'bg-blue-900/30 text-blue-300' : 'bg-gray-800 text-gray-400'}">{rule.access_level}</span>
                      </td>
                      <td class="px-3 py-2 text-gray-500">{rule.state}</td>
                      {#if createdFs.share_proto !== 'NFS'}
                        <td class="px-3 py-2">
                          {#if rule.access_key}
                            <div class="flex items-center gap-1.5">
                              <code class="text-gray-400 font-mono truncate max-w-[120px]">{rule.access_key.slice(0, 12)}…</code>
                              <button onclick={() => copyKey(rule.access_key!, rule.id)}
                                class="text-gray-600 hover:text-gray-300 transition-colors">
                                {copiedKey === rule.id ? '✓' : '⎘'}
                              </button>
                            </div>
                          {:else}
                            <span class="text-gray-600">대기 중</span>
                          {/if}
                        </td>
                      {/if}
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          {:else}
            <p class="text-xs text-gray-600 mb-4">아직 추가된 접근 규칙이 없습니다.</p>
          {/if}

          <div class="flex justify-end gap-3 mt-2">
            <button onclick={closeWizard} class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">건너뛰기</button>
            <button onclick={closeWizard} class="px-5 py-2 bg-green-700 hover:bg-green-600 text-white text-sm font-medium rounded-lg transition-colors">완료</button>
          </div>
        {/if}

      </div>
    </div>
  </div>
{/if}

<!-- ===== 메인 페이지 ===== -->
<div class="p-4 md:p-8">
  <div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold text-white">파일 스토리지</h1>
    <div class="flex items-center gap-2">
      <AutoRefreshToggle bind:active={autoRefresh} intervalSeconds={10} />
      <RefreshButton refreshing={refreshing} onclick={forceRefresh} />
      <button onclick={openWizard} class="bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">+ 파일 스토리지 생성</button>
    </div>
  </div>

  {#if quota}
    <div class="flex items-center gap-6 mb-6 bg-gray-900 border border-gray-800 rounded-lg px-5 py-3">
      <span class="text-xs text-gray-500 uppercase tracking-wide">쿼터</span>
      {#each [
        { label: 'File Storage', item: quota.shares },
        { label: '용량', item: quota.gigabytes, unit: 'GB' },
        { label: 'Share Networks', item: quota.share_networks },
      ] as q}
        <div class="flex items-center gap-1.5">
          <span class="text-xs text-gray-400">{q.label}:</span>
          <span class="text-xs font-medium {q.item.limit > 0 && q.item.in_use / q.item.limit > 0.8 ? 'text-orange-400' : 'text-white'}">{q.item.in_use}{q.unit ?? ''}</span>
          {#if q.item.limit > 0}<span class="text-xs text-gray-600">/ {q.item.limit}{q.unit ?? ''}</span>{/if}
        </div>
      {/each}
    </div>
  {/if}

  {#if error}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>{/if}

  {#if loading}
    <LoadingSkeleton variant="table" rows={5} />
  {:else if fileStorages.length === 0}
    <div class="text-center py-20 text-gray-600">
      <div class="text-5xl mb-4">🗂️</div>
      <p class="text-lg">파일 스토리지가 없습니다</p>
      <button onclick={openWizard} class="text-blue-400 hover:text-blue-300 text-sm mt-2 inline-block">첫 파일 스토리지를 생성하세요 →</button>
    </div>
  {:else}
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
            <th class="text-left py-3 pr-6">이름</th>
            <th class="text-left py-3 pr-6">상태</th>
            <th class="text-left py-3 pr-4">크기</th>
            <th class="text-left py-3 pr-4">프로토콜</th>
            <th class="text-left py-3 pr-6">라이브러리</th>
            <th class="text-left py-3 pr-6">Export Location</th>
            <th class="text-right py-3">액션</th>
          </tr>
        </thead>
        <tbody>
          {#each fileStorages as fs (fs.id)}
            <tr class="border-b border-gray-800/50 hover:bg-gray-800/50 transition-colors">
              <td class="py-3 pr-6 font-medium">
                <button onclick={() => openDetailPanel(fs.id)} class="text-white hover:text-blue-400 transition-colors text-left">
                  {#if fs.name}<span>{fs.name}</span>{:else}<span class="text-gray-400 font-mono text-xs">{fs.id}</span>{/if}
                </button>
              </td>
              <td class="py-3 pr-6"><span class="px-2 py-0.5 rounded text-xs font-medium {statusColor[fs.status] ?? 'text-gray-400 bg-gray-800'}">{fs.status}</span></td>
              <td class="py-3 pr-4 text-gray-400 text-xs">{fs.size} GB</td>
              <td class="py-3 pr-4 text-gray-400 text-xs">{fs.share_proto}</td>
              <td class="py-3 pr-6 text-xs">
                {#if fs.library_name}
                  <span class="px-1.5 py-0.5 bg-blue-900/40 text-blue-300 rounded text-xs">{fs.library_name}{fs.library_version ? ` v${fs.library_version}` : ''}</span>
                {:else}
                  <span class="text-gray-600">-</span>
                {/if}
              </td>
              <td class="py-3 pr-6 text-xs max-w-[200px]">
                {#if fs.export_locations && fs.export_locations.length > 0}
                  <div class="flex items-center gap-1.5">
                    <span class="text-gray-500 font-mono truncate">{fs.export_locations[0].slice(-32)}</span>
                    <button onclick={(e) => { e.stopPropagation(); copyExportPath(fs.export_locations[0], fs.id); }}
                      class="shrink-0 text-gray-600 hover:text-gray-400 transition-colors" title="경로 복사">
                      {copiedExport === fs.id ? '✓' : '⎘'}
                    </button>
                  </div>
                {:else}
                  <span class="text-gray-600">-</span>
                {/if}
              </td>
              <td class="py-3 text-right">
                <button onclick={(e) => { e.stopPropagation(); deleteFileStorage(fs.id, fs.name); }} disabled={deleting === fs.id}
                  class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-1 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors">
                  {deleting === fs.id ? '삭제 중...' : '삭제'}
                </button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<!-- File Storage Detail Panel -->
{#if selectedId}
  <SlidePanel onClose={closeDetailPanel} width="w-full md:w-[60vw] max-w-2xl">
    <FileStorageDetailPanel
      fileStorageId={selectedId}
      onClose={closeDetailPanel}
      onDeleted={() => { fetchFileStorages(); closeDetailPanel(); }}
    />
  </SlidePanel>
{/if}
