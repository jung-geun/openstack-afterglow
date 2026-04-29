<script lang="ts">
  import { auth, isAdmin } from '$lib/stores/auth';
  import { api, ApiError } from '$lib/api/client';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';

  import StatusChip from '$lib/components/ui/StatusChip.svelte';
  import PageHeader from '$lib/components/ui/PageHeader.svelte';
  import SlidePanel from '$lib/components/SlidePanel.svelte';

  interface LayerInfo {
    id: string;
    name: string;
    version: string;
    sealed: boolean;
  }

  interface TemplateInfo {
    name: string;
    version: number;
    created_at: string;
    created_by: string;
    parent_version: number | null;
    ubuntu_base: string;
    leaf_layer_id: string;
    note: string | null;
    resolved_stack: LayerInfo[] | null;
  }

  let templates = $state<TemplateInfo[]>([]);
  let loading = $state(true);
  let refreshing = $state(false);
  let error = $state('');
  let selectedTemplate = $state<TemplateInfo | null>(null);
  let panelOpen = $state(false);
  let loadingDetail = $state(false);

  // 새 템플릿 생성 폼
  let showCreateForm = $state(false);
  let sealedLayers = $state<LayerInfo[]>([]);
  let newName = $state('');
  let newVersion = $state(1);
  let newUbuntuBase = $state('');
  let newLeafLayerId = $state('');
  let newNote = $state('');
  let submitting = $state(false);

  const token = $derived($auth.token ?? undefined);
  const projectId = $derived($auth.projectId ?? undefined);

  let initialLoaded = false;

  async function loadTemplates() {
    if (!initialLoaded) loading = true;
    else refreshing = true;
    error = '';
    try {
      templates = await api.get<TemplateInfo[]>('/api/union/templates', token, projectId);
      initialLoaded = true;
    } catch (e) {
      error = e instanceof ApiError ? e.message : '템플릿 로드 실패';
      templates = [];
    } finally {
      loading = false;
      refreshing = false;
    }
  }

  $effect(() => {
    if (token) loadTemplates();
  });

  async function loadSealedLayers() {
    try {
      const all = await api.get<LayerInfo[]>('/api/union/layers?limit=200', token, projectId);
      sealedLayers = all.filter(l => l.sealed);
    } catch {}
  }

  async function openTemplate(t: TemplateInfo) {
    panelOpen = true;
    loadingDetail = true;
    try {
      const detail = await api.get<TemplateInfo>(`/api/union/templates/${encodeURIComponent(t.name)}/${t.version}`, token, projectId);
      selectedTemplate = detail;
    } catch {
      selectedTemplate = t;
    } finally {
      loadingDetail = false;
    }
  }

  async function handleCreateTemplate(e: Event) {
    e.preventDefault();
    if (submitting) return;
    error = '';
    submitting = true;
    try {
      await api.post('/api/union/templates', {
        name: newName.trim(),
        version: newVersion,
        ubuntu_base: newUbuntuBase.trim(),
        leaf_layer_id: newLeafLayerId,
        note: newNote.trim() || null,
      }, token, projectId);
      showCreateForm = false;
      newName = ''; newVersion = 1; newUbuntuBase = ''; newLeafLayerId = ''; newNote = '';
      await loadTemplates();
    } catch (e) {
      error = e instanceof ApiError ? e.message : '템플릿 생성 실패';
    } finally {
      submitting = false;
    }
  }

  function formatDate(dt: string): string {
    return new Date(dt).toLocaleDateString('ko-KR', { year: 'numeric', month: '2-digit', day: '2-digit' });
  }
</script>

<div class="flex flex-col h-full overflow-auto bg-gray-900 text-gray-100 p-6">
  <PageHeader title="템플릿" breadcrumb="라이브러리">
    {#snippet action()}
      <div class="flex items-center gap-2">
        {#if $isAdmin}
          <button
            onclick={() => { showCreateForm = !showCreateForm; if (showCreateForm) loadSealedLayers(); }}
            class="px-3 py-1.5 text-sm bg-blue-600 hover:bg-blue-500 rounded-md transition-colors"
          >+ 새 템플릿</button>
        {/if}
        <button onclick={loadTemplates} class="text-xs text-gray-400 hover:text-white transition-colors px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600 flex items-center gap-1.5">새로고침</button>
      </div>
    {/snippet}
  </PageHeader>

  {#if error}
    <div class="mb-4 p-3 bg-red-900/40 border border-red-700 rounded-md text-red-300 text-sm">{error}</div>
  {/if}

  <!-- 생성 폼 -->
  {#if showCreateForm && $isAdmin}
    <div class="mb-6 bg-gray-800 rounded-lg border border-gray-700 p-5">
      <h3 class="text-sm font-medium mb-4">새 템플릿 생성</h3>
      <form onsubmit={handleCreateTemplate} class="grid grid-cols-2 gap-4">
        <div>
          <label class="block text-xs text-gray-400 mb-1">이름 *</label>
          <input bind:value={newName} type="text" placeholder="예: ml-pytorch" required
            class="w-full px-3 py-2 text-sm bg-gray-700 border border-gray-600 rounded-md focus:outline-none focus:border-blue-500" />
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1">버전 *</label>
          <input bind:value={newVersion} type="number" min="1" required
            class="w-full px-3 py-2 text-sm bg-gray-700 border border-gray-600 rounded-md focus:outline-none focus:border-blue-500" />
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1">Ubuntu Base *</label>
          <input bind:value={newUbuntuBase} type="text" placeholder="ubuntu-24.04" required
            class="w-full px-3 py-2 text-sm bg-gray-700 border border-gray-600 rounded-md focus:outline-none focus:border-blue-500" />
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1">Leaf 레이어 *</label>
          <select bind:value={newLeafLayerId} required
            class="w-full px-3 py-2 text-sm bg-gray-700 border border-gray-600 rounded-md focus:outline-none focus:border-blue-500">
            <option value="">레이어 선택...</option>
            {#each sealedLayers as l}
              <option value={l.id}>{l.name} ({l.version})</option>
            {/each}
          </select>
        </div>
        <div class="col-span-2">
          <label class="block text-xs text-gray-400 mb-1">설명 (선택)</label>
          <input bind:value={newNote} type="text" placeholder="템플릿 설명"
            class="w-full px-3 py-2 text-sm bg-gray-700 border border-gray-600 rounded-md focus:outline-none focus:border-blue-500" />
        </div>
        <div class="col-span-2 flex gap-2">
          <button type="submit" disabled={submitting}
            class="px-4 py-2 text-sm bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-md">
            {submitting ? '생성 중...' : '생성'}
          </button>
          <button type="button" onclick={() => showCreateForm = false}
            class="px-4 py-2 text-sm bg-gray-700 hover:bg-gray-600 rounded-md">취소</button>
        </div>
      </form>
    </div>
  {/if}

  {#if loading}
    <LoadingSkeleton rows={5} />
  {:else if templates.length === 0}
    <div class="flex flex-col items-center justify-center flex-1 text-gray-500">
      <p>등록된 템플릿이 없습니다</p>
    </div>
  {:else}
    <div class:opacity-60={refreshing} class:pointer-events-none={refreshing}>
    <div class="rounded-lg border border-gray-700 overflow-hidden">
      <table class="w-full text-sm">
        <thead class="bg-gray-800 text-gray-400 text-xs uppercase">
          <tr>
            <th class="px-4 py-3 text-left">이름</th>
            <th class="px-4 py-3 text-left">버전</th>
            <th class="px-4 py-3 text-left hidden md:table-cell">Ubuntu Base</th>
            <th class="px-4 py-3 text-left hidden lg:table-cell">설명</th>
            <th class="px-4 py-3 text-left hidden lg:table-cell">생성일</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-700/50">
          {#each templates as tmpl}
            <tr
              class="hover:bg-gray-800/50 cursor-pointer transition-colors"
              onclick={() => openTemplate(tmpl)}
            >
              <td class="px-4 py-3 font-medium">{tmpl.name}</td>
              <td class="px-4 py-3 text-gray-400">v{tmpl.version}</td>
              <td class="px-4 py-3 hidden md:table-cell text-gray-400 text-xs">{tmpl.ubuntu_base}</td>
              <td class="px-4 py-3 hidden lg:table-cell text-gray-500 text-xs">{tmpl.note ?? '-'}</td>
              <td class="px-4 py-3 hidden lg:table-cell text-gray-500 text-xs">{formatDate(tmpl.created_at)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    </div>
  {/if}
</div>

<!-- 템플릿 상세 슬라이드 패널 -->
{#if panelOpen}
  <SlidePanel onClose={() => { panelOpen = false; selectedTemplate = null; }}>
    {#if loadingDetail}
      <div class="p-6"><LoadingSkeleton rows={4} /></div>
    {:else if selectedTemplate}
      <div class="p-6">
        <h2 class="text-lg font-semibold mb-1">{selectedTemplate.name}</h2>
        <p class="text-sm text-gray-400 mb-5">버전 {selectedTemplate.version} · {selectedTemplate.ubuntu_base}</p>

        {#if selectedTemplate.note}
          <p class="text-sm text-gray-300 mb-5">{selectedTemplate.note}</p>
        {/if}

        <dl class="space-y-3 text-sm mb-6">
          <div>
            <dt class="text-gray-500 text-xs">Leaf Layer ID</dt>
            <dd class="font-mono text-xs text-gray-300 break-all mt-0.5">{selectedTemplate.leaf_layer_id}</dd>
          </div>
          <div>
            <dt class="text-gray-500 text-xs">생성자</dt>
            <dd class="text-gray-300 mt-0.5">{selectedTemplate.created_by}</dd>
          </div>
          <div>
            <dt class="text-gray-500 text-xs">생성일</dt>
            <dd class="text-gray-300 mt-0.5">{formatDate(selectedTemplate.created_at)}</dd>
          </div>
        </dl>

        {#if selectedTemplate.resolved_stack && selectedTemplate.resolved_stack.length > 0}
          <div>
            <h3 class="text-sm font-medium text-gray-300 mb-3">레이어 스택 (base → leaf)</h3>
            <div class="space-y-2">
              {#each selectedTemplate.resolved_stack as layer, i}
                <div class="flex items-center gap-3 p-2 rounded bg-gray-700/40">
                  <div class="w-5 h-5 rounded-full bg-gray-600 flex items-center justify-center text-xs text-gray-300">{i + 1}</div>
                  <div class="flex-1 min-w-0">
                    <div class="text-sm text-gray-200">{layer.name}</div>
                    <div class="text-xs text-gray-500">{layer.version}</div>
                  </div>
                  <StatusChip status={layer.sealed ? 'sealed' : 'draft'} />
                </div>
              {/each}
            </div>
          </div>
        {/if}

        <a
          href="/dashboard/library/{encodeURIComponent(selectedTemplate.leaf_layer_id)}"
          class="mt-5 inline-block text-sm text-blue-400 hover:text-blue-300"
        >Leaf 레이어 상세 →</a>
      </div>
    {/if}
  </SlidePanel>
{/if}
