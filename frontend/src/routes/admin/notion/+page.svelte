<script lang="ts">
  import { auth } from '$lib/stores/auth';
  import { api, ApiError } from '$lib/api/client';
  import { env } from '$env/dynamic/public';

  function getBaseUrl(): string {
    if (typeof window !== 'undefined') {
      return env.PUBLIC_API_BASE || `${window.location.protocol}//${window.location.hostname}:8000`;
    }
    return env.PUBLIC_API_BASE || 'http://backend:8000';
  }

  interface NotionTarget {
    id: number;
    label: string;
    api_key: string; // masked
    database_id: string;
    users_database_id: string;
    hypervisors_database_id: string;
    gpu_spec_database_id: string;
    enabled: boolean;
    interval_minutes: number;
    last_sync: string | null;
    hypervisors_last_sync: string | null;
    gpu_spec_last_sync: string | null;
    created_at: string;
    updated_at: string;
  }

  let targets = $state<NotionTarget[]>([]);
  let loading = $state(true);
  let error = $state('');

  // 추가 폼 상태
  let showAddForm = $state(false);
  let addLabel = $state('기본');
  let addApiKey = $state('');
  let addDatabaseId = $state('');
  let addEnabled = $state(true);
  let addIntervalMinutes = $state(5);
  let addUsersDatabaseId = $state('');
  let addHypervisorsDatabaseId = $state('');
  let addGpuSpecDatabaseId = $state('');
  let adding = $state(false);
  let addError = $state('');

  // 수정 중인 타겟 ID
  let editingId = $state<number | null>(null);
  let editLabel = $state('');
  let editApiKey = $state('');
  let editDatabaseId = $state('');
  let editEnabled = $state(true);
  let editIntervalMinutes = $state(5);
  let editUsersDatabaseId = $state('');
  let editHypervisorsDatabaseId = $state('');
  let editGpuSpecDatabaseId = $state('');
  let editSaving = $state(false);
  let editError = $state('');

  // 테스트 상태 (target_id → message/error)
  let testingId = $state<number | null>(null);
  let testMessages = $state<Record<number, string>>({});
  let testErrors = $state<Record<number, string>>({});

  async function fetchTargets() {
    loading = true;
    try {
      targets = await api.get<NotionTarget[]>(
        '/api/admin/notion/targets',
        $auth.token ?? undefined,
        $auth.projectId ?? undefined
      );
      error = '';
    } catch (e) {
      error = e instanceof ApiError ? `조회 실패 (${e.status})` : '서버 오류';
    } finally {
      loading = false;
    }
  }

  async function addTarget() {
    if (!addApiKey) { addError = 'API Key를 입력하세요'; return; }
    if (!addDatabaseId) { addError = '인스턴스 Database ID를 입력하세요'; return; }
    if (addIntervalMinutes < 1 || addIntervalMinutes > 1440) {
      addError = '동기화 간격은 1~1440분 사이여야 합니다'; return;
    }
    adding = true; addError = '';
    try {
      await api.post(
        '/api/admin/notion/targets',
        {
          label: addLabel,
          api_key: addApiKey,
          database_id: addDatabaseId,
          enabled: addEnabled,
          interval_minutes: addIntervalMinutes,
          users_database_id: addUsersDatabaseId,
          hypervisors_database_id: addHypervisorsDatabaseId,
          gpu_spec_database_id: addGpuSpecDatabaseId,
        },
        $auth.token ?? undefined,
        $auth.projectId ?? undefined
      );
      showAddForm = false;
      addApiKey = ''; addDatabaseId = ''; addLabel = '기본';
      addUsersDatabaseId = ''; addHypervisorsDatabaseId = ''; addGpuSpecDatabaseId = '';
      addEnabled = true; addIntervalMinutes = 5;
      await fetchTargets();
    } catch (e) {
      addError = e instanceof ApiError ? e.message : '추가 실패';
    } finally {
      adding = false;
    }
  }

  function startEdit(t: NotionTarget) {
    editingId = t.id;
    editLabel = t.label;
    editApiKey = '';
    editDatabaseId = t.database_id;
    editEnabled = t.enabled;
    editIntervalMinutes = t.interval_minutes;
    editUsersDatabaseId = t.users_database_id;
    editHypervisorsDatabaseId = t.hypervisors_database_id;
    editGpuSpecDatabaseId = t.gpu_spec_database_id;
    editError = '';
  }

  async function saveEdit() {
    if (!editingId) return;
    editSaving = true; editError = '';
    try {
      const data: Record<string, unknown> = {
        label: editLabel,
        database_id: editDatabaseId,
        enabled: editEnabled,
        interval_minutes: editIntervalMinutes,
        users_database_id: editUsersDatabaseId,
        hypervisors_database_id: editHypervisorsDatabaseId,
        gpu_spec_database_id: editGpuSpecDatabaseId,
      };
      if (editApiKey) data.api_key = editApiKey;
      await api.patch(
        `/api/admin/notion/targets/${editingId}`,
        data,
        $auth.token ?? undefined,
        $auth.projectId ?? undefined
      );
      editingId = null;
      await fetchTargets();
    } catch (e) {
      editError = e instanceof ApiError ? e.message : '저장 실패';
    } finally {
      editSaving = false;
    }
  }

  async function deleteTarget(id: number) {
    if (!confirm('이 연동 대상을 삭제하시겠습니까?')) return;
    try {
      await api.delete(
        `/api/admin/notion/targets/${id}`,
        $auth.token ?? undefined,
        $auth.projectId ?? undefined
      );
      await fetchTargets();
    } catch (e) {
      alert('삭제 실패');
    }
  }

  async function testTarget(id: number) {
    testingId = id;
    testMessages = { ...testMessages, [id]: '' };
    testErrors = { ...testErrors, [id]: '' };
    try {
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if ($auth.token) headers['X-Auth-Token'] = $auth.token;
      if ($auth.projectId) headers['X-Project-Id'] = $auth.projectId;
      const resp = await fetch(`${getBaseUrl()}/api/admin/notion/targets/${id}/test`, {
        method: 'POST',
        headers,
        body: '{}',
        signal: AbortSignal.timeout(120_000),
      });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({ detail: resp.statusText }));
        throw new ApiError(resp.status, body?.detail || resp.statusText);
      }
      const result = await resp.json();
      testMessages = { ...testMessages, [id]: result.message };
      await fetchTargets();
    } catch (e) {
      testErrors = {
        ...testErrors,
        [id]: e instanceof ApiError
          ? e.message
          : (e instanceof Error && e.name === 'TimeoutError')
            ? '동기화 시간 초과 (2분)'
            : '테스트 실패',
      };
    } finally {
      testingId = null;
    }
  }

  function formatDate(s: string | null | undefined): string {
    if (!s) return '-';
    return s.replace('T', ' ').slice(0, 19) + ' UTC';
  }

  $effect(() => {
    if ($auth.token) fetchTargets();
  });
</script>

<div class="p-4 md:p-8 max-w-3xl">
  <div class="flex items-center justify-between mb-6">
    <div>
      <h1 class="text-2xl font-bold text-white">Notion 연동</h1>
      <p class="text-sm text-gray-400 mt-1">OpenStack 리소스를 여러 Notion DB에 동시에 동기화합니다.</p>
    </div>
    <button
      onclick={() => { showAddForm = !showAddForm; addError = ''; }}
      class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-colors"
    >
      {showAddForm ? '취소' : '+ 연결 추가'}
    </button>
  </div>

  {#if error}
    <div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>
  {/if}

  <!-- 추가 폼 -->
  {#if showAddForm}
    <div class="bg-gray-900 border border-blue-800 rounded-lg p-5 mb-6">
      <h2 class="text-sm font-semibold text-blue-400 mb-4">새 연동 대상 추가</h2>
      <div class="space-y-3">
        <div>
          <label class="block text-xs text-gray-400 mb-1">레이블 (식별용)</label>
          <input bind:value={addLabel} type="text" placeholder="예: 운영팀 DB"
            class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1">Notion API Key <span class="text-red-400">*</span></label>
          <input bind:value={addApiKey} type="password" placeholder="ntn_..."
            class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 font-mono" />
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1">인스턴스 Database ID <span class="text-red-400">*</span></label>
          <input bind:value={addDatabaseId} type="text" placeholder="32자리 UUID"
            class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 font-mono" />
        </div>
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-xs text-gray-400 mb-1">사용자 DB ID <span class="text-gray-600">(선택)</span></label>
            <input bind:value={addUsersDatabaseId} type="text" placeholder="People DB"
              class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 font-mono" />
          </div>
          <div>
            <label class="block text-xs text-gray-400 mb-1">하이퍼바이저 DB ID <span class="text-gray-600">(선택)</span></label>
            <input bind:value={addHypervisorsDatabaseId} type="text" placeholder="Hypervisor DB"
              class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 font-mono" />
          </div>
        </div>
        <div>
          <label class="block text-xs text-gray-400 mb-1">GPU Spec DB ID <span class="text-gray-600">(선택)</span></label>
          <input bind:value={addGpuSpecDatabaseId} type="text" placeholder="GPU Spec DB"
            class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 font-mono" />
        </div>
        <div class="flex gap-4 items-end">
          <div>
            <label class="block text-xs text-gray-400 mb-1">동기화 간격 (분)</label>
            <input bind:value={addIntervalMinutes} type="number" min="1" max="1440"
              class="w-24 bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
          </div>
          <label class="flex items-center gap-2 cursor-pointer pb-2">
            <input bind:checked={addEnabled} type="checkbox"
              class="w-4 h-4 rounded border-gray-600 bg-gray-800 text-blue-600 focus:ring-blue-500" />
            <span class="text-sm text-gray-300">활성화</span>
          </label>
        </div>
      </div>
      {#if addError}
        <div class="mt-3 text-red-400 text-sm">{addError}</div>
      {/if}
      <div class="mt-4">
        <button onclick={addTarget} disabled={adding}
          class="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors">
          {adding ? '추가 중...' : '연결 검증 및 추가'}
        </button>
      </div>
    </div>
  {/if}

  {#if loading}
    <div class="space-y-3">
      {#each [0, 1] as _}
        <div class="animate-pulse bg-gray-900 rounded-lg h-32"></div>
      {/each}
    </div>
  {:else if targets.length === 0}
    <div class="bg-gray-900 border border-gray-800 rounded-lg p-8 text-center">
      <p class="text-gray-500 text-sm">등록된 Notion 연동 대상이 없습니다.</p>
      <p class="text-gray-600 text-xs mt-1">"연결 추가" 버튼을 눌러 시작하세요.</p>
    </div>
  {:else}
    <div class="space-y-4">
      {#each targets as target (target.id)}
        <div class="bg-gray-900 border border-gray-800 rounded-lg p-5">
          {#if editingId === target.id}
            <!-- 수정 폼 -->
            <div class="space-y-3">
              <div class="flex items-center justify-between mb-2">
                <h3 class="text-sm font-semibold text-blue-400">수정 중</h3>
                <button onclick={() => { editingId = null; }} class="text-xs text-gray-500 hover:text-gray-300">취소</button>
              </div>
              <div>
                <label class="block text-xs text-gray-400 mb-1">레이블</label>
                <input bind:value={editLabel} type="text"
                  class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
              </div>
              <div>
                <label class="block text-xs text-gray-400 mb-1">API Key <span class="text-gray-600">(변경 시에만 입력)</span></label>
                <input bind:value={editApiKey} type="password" placeholder="변경하지 않으면 비워두세요"
                  class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 font-mono" />
              </div>
              <div>
                <label class="block text-xs text-gray-400 mb-1">인스턴스 Database ID</label>
                <input bind:value={editDatabaseId} type="text"
                  class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 font-mono" />
              </div>
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="block text-xs text-gray-400 mb-1">사용자 DB ID</label>
                  <input bind:value={editUsersDatabaseId} type="text"
                    class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 font-mono" />
                </div>
                <div>
                  <label class="block text-xs text-gray-400 mb-1">하이퍼바이저 DB ID</label>
                  <input bind:value={editHypervisorsDatabaseId} type="text"
                    class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 font-mono" />
                </div>
              </div>
              <div>
                <label class="block text-xs text-gray-400 mb-1">GPU Spec DB ID</label>
                <input bind:value={editGpuSpecDatabaseId} type="text"
                  class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 font-mono" />
              </div>
              <div class="flex gap-4 items-end">
                <div>
                  <label class="block text-xs text-gray-400 mb-1">동기화 간격 (분)</label>
                  <input bind:value={editIntervalMinutes} type="number" min="1" max="1440"
                    class="w-24 bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
                </div>
                <label class="flex items-center gap-2 cursor-pointer pb-2">
                  <input bind:checked={editEnabled} type="checkbox"
                    class="w-4 h-4 rounded border-gray-600 bg-gray-800 text-blue-600 focus:ring-blue-500" />
                  <span class="text-sm text-gray-300">활성화</span>
                </label>
              </div>
              {#if editError}
                <div class="text-red-400 text-sm">{editError}</div>
              {/if}
              <button onclick={saveEdit} disabled={editSaving}
                class="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors">
                {editSaving ? '저장 중...' : '저장'}
              </button>
            </div>
          {:else}
            <!-- 카드 뷰 -->
            <div class="flex items-start justify-between">
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 mb-1">
                  <span class="text-white font-medium">{target.label}</span>
                  {#if target.enabled}
                    <span class="text-xs text-green-400 bg-green-900/30 px-1.5 py-0.5 rounded">활성</span>
                  {:else}
                    <span class="text-xs text-gray-500 bg-gray-800 px-1.5 py-0.5 rounded">비활성</span>
                  {/if}
                  <span class="text-xs text-gray-500">{target.interval_minutes}분 간격</span>
                </div>
                <div class="text-xs text-gray-500 font-mono truncate">{target.api_key}</div>
                <dl class="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                  <div>
                    <dt class="text-gray-600 inline">인스턴스 DB: </dt>
                    <dd class="text-gray-400 font-mono inline">{target.database_id || '-'}</dd>
                  </div>
                  <div>
                    <dt class="text-gray-600 inline">마지막 동기화: </dt>
                    <dd class="text-gray-400 inline">{formatDate(target.last_sync)}</dd>
                  </div>
                  {#if target.hypervisors_database_id}
                    <div>
                      <dt class="text-gray-600 inline">하이퍼바이저 DB: </dt>
                      <dd class="text-gray-400 font-mono inline">{target.hypervisors_database_id}</dd>
                    </div>
                    <div>
                      <dt class="text-gray-600 inline">하이퍼바이저 동기화: </dt>
                      <dd class="text-gray-400 inline">{formatDate(target.hypervisors_last_sync)}</dd>
                    </div>
                  {/if}
                  {#if target.gpu_spec_database_id}
                    <div>
                      <dt class="text-gray-600 inline">GPU Spec DB: </dt>
                      <dd class="text-gray-400 font-mono inline">{target.gpu_spec_database_id}</dd>
                    </div>
                    <div>
                      <dt class="text-gray-600 inline">GPU spec 동기화: </dt>
                      <dd class="text-gray-400 inline">{formatDate(target.gpu_spec_last_sync)}</dd>
                    </div>
                  {/if}
                </dl>
              </div>
              <div class="flex items-center gap-2 ml-4 shrink-0">
                <button onclick={() => testTarget(target.id)} disabled={testingId === target.id}
                  class="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-xs rounded-lg transition-colors">
                  {testingId === target.id ? '동기화 중...' : '지금 동기화'}
                </button>
                <button onclick={() => startEdit(target)}
                  class="px-3 py-1.5 border border-gray-700 hover:border-gray-500 text-gray-400 hover:text-gray-200 text-xs rounded-lg transition-colors">
                  수정
                </button>
                <button onclick={() => deleteTarget(target.id)}
                  class="px-3 py-1.5 border border-red-900 hover:border-red-700 text-red-400 hover:text-red-300 text-xs rounded-lg transition-colors">
                  삭제
                </button>
              </div>
            </div>
            {#if testMessages[target.id]}
              <div class="mt-2 text-green-400 text-xs">{testMessages[target.id]}</div>
            {/if}
            {#if testErrors[target.id]}
              <div class="mt-2 text-red-400 text-xs">{testErrors[target.id]}</div>
            {/if}
          {/if}
        </div>
      {/each}
    </div>
  {/if}

  <!-- 안내 -->
  <div class="mt-6 bg-gray-900/50 border border-gray-800 rounded-lg p-5">
    <h3 class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">설정 방법</h3>
    <ol class="text-xs text-gray-500 space-y-1.5 list-decimal list-inside">
      <li>
        <a href="https://www.notion.so/profile/integrations" target="_blank" class="text-blue-500 hover:text-blue-400">Notion Integrations</a>에서 Internal Integration 생성
      </li>
      <li>Notion에서 빈 Database 페이지 생성 후 Integration 연결 추가</li>
      <li>Database URL에서 32자리 ID 복사</li>
      <li>"연결 추가" 버튼으로 등록 — 필요한 컬럼이 자동 생성됩니다</li>
      <li>여러 연동 대상을 등록하면 동일한 데이터를 각 Notion DB에 동시에 동기화합니다</li>
    </ol>
  </div>
</div>
