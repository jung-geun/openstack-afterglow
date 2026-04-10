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

  interface NotionConfig {
    configured: boolean;
    api_key_masked?: string;
    database_id?: string;
    enabled?: boolean;
    interval_minutes?: number;
    last_sync?: string | null;
    users_database_id?: string;
    hypervisors_database_id?: string;
    hypervisors_last_sync?: string | null;
  }

  let config = $state<NotionConfig | null>(null);
  let loading = $state(true);
  let error = $state('');

  // 폼
  let apiKey = $state('');
  let databaseId = $state('');
  let enabled = $state(true);
  let intervalMinutes = $state(5);
  let usersDatabaseId = $state('');
  let hypervisorsDatabaseId = $state('');

  let saving = $state(false);
  let saveMessage = $state('');
  let saveError = $state('');

  let testing = $state(false);
  let testMessage = $state('');
  let testError = $state('');

  let deleting = $state(false);

  async function fetchConfig() {
    loading = true;
    try {
      config = await api.get<NotionConfig>(
        '/api/admin/notion/config',
        $auth.token ?? undefined,
        $auth.projectId ?? undefined
      );
      if (config?.configured) {
        databaseId = config.database_id ?? '';
        enabled = config.enabled ?? true;
        intervalMinutes = config.interval_minutes ?? 5;
        usersDatabaseId = config.users_database_id ?? '';
        hypervisorsDatabaseId = config.hypervisors_database_id ?? '';
        apiKey = '';
      }
      error = '';
    } catch (e) {
      error = e instanceof ApiError ? `조회 실패 (${e.status})` : '서버 오류';
    } finally {
      loading = false;
    }
  }

  async function saveConfig() {
    if (!apiKey && !config?.configured) {
      saveError = 'API Key를 입력하세요';
      return;
    }
    if (!databaseId) {
      saveError = 'Database ID를 입력하세요';
      return;
    }

    saving = true;
    saveMessage = '';
    saveError = '';
    try {
      // 기존 설정이 있고 API Key를 비워둔 경우, 기존 키 유지 불가 → 새로 입력 필요
      if (!apiKey) {
        saveError = 'API Key를 입력하세요 (보안상 기존 키는 표시되지 않습니다)';
        saving = false;
        return;
      }
      const result = await api.post<{ status: string; message: string }>(
        '/api/admin/notion/config',
        {
          api_key: apiKey,
          database_id: databaseId,
          enabled,
          interval_minutes: intervalMinutes,
          users_database_id: usersDatabaseId,
          hypervisors_database_id: hypervisorsDatabaseId,
        },
        $auth.token ?? undefined,
        $auth.projectId ?? undefined
      );
      saveMessage = result.message;
      apiKey = '';
      await fetchConfig();
    } catch (e) {
      saveError = e instanceof ApiError ? e.message : '저장 실패';
    } finally {
      saving = false;
    }
  }

  async function testSync() {
    testing = true;
    testMessage = '';
    testError = '';
    try {
      // 동기화는 인스턴스 수에 따라 오래 걸릴 수 있으므로 타임아웃 120초
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if ($auth.token) headers['X-Auth-Token'] = $auth.token;
      if ($auth.projectId) headers['X-Project-Id'] = $auth.projectId;
      const resp = await fetch(`${getBaseUrl()}/api/admin/notion/test`, {
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
      testMessage = result.message;
      await fetchConfig();
    } catch (e) {
      testError = e instanceof ApiError ? e.message : (e instanceof Error && e.name === 'TimeoutError') ? '동기화 시간 초과 (2분). 인스턴스가 많으면 백그라운드 동기화를 사용하세요.' : '테스트 실패';
    } finally {
      testing = false;
    }
  }

  async function deleteConfig() {
    if (!confirm('Notion 연동을 비활성화하시겠습니까? 설정이 삭제됩니다.')) return;
    deleting = true;
    try {
      await api.delete('/api/admin/notion/config', $auth.token ?? undefined, $auth.projectId ?? undefined);
      config = { configured: false };
      apiKey = '';
      databaseId = '';
      enabled = true;
      intervalMinutes = 5;
      usersDatabaseId = '';
      hypervisorsDatabaseId = '';
    } catch (e) {
      alert('삭제 실패');
    } finally {
      deleting = false;
    }
  }

  function formatDate(s: string | null | undefined): string {
    if (!s) return '-';
    return s.replace('T', ' ').slice(0, 19) + ' UTC';
  }

  $effect(() => {
    if ($auth.token) fetchConfig();
  });
</script>

<div class="p-4 md:p-8 max-w-2xl">
  <h1 class="text-2xl font-bold text-white mb-6">Notion 연동</h1>
  <p class="text-sm text-gray-400 mb-6">
    Notion Database에 시스템 리소스 현황을 주기적으로 동기화합니다. 인스턴스 DB는 필수, 사용자 매핑 및 하이퍼바이저 DB는 선택입니다.
  </p>

  {#if error}
    <div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>
  {/if}

  {#if loading}
    <div class="animate-pulse space-y-4">
      <div class="h-10 bg-gray-800 rounded-lg"></div>
      <div class="h-10 bg-gray-800 rounded-lg"></div>
      <div class="h-10 bg-gray-800 rounded-lg"></div>
    </div>
  {:else}

    <!-- 현재 상태 -->
    {#if config?.configured}
      <div class="bg-gray-900 border border-gray-800 rounded-lg p-5 mb-6">
        <h2 class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">현재 설정</h2>
        <dl class="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
          <div>
            <dt class="text-xs text-gray-500">상태</dt>
            <dd>
              {#if config.enabled}
                <span class="text-green-400 font-medium">활성</span>
              {:else}
                <span class="text-gray-500">비활성</span>
              {/if}
            </dd>
          </div>
          <div>
            <dt class="text-xs text-gray-500">동기화 간격</dt>
            <dd class="text-gray-300">{config.interval_minutes}분</dd>
          </div>
          <div>
            <dt class="text-xs text-gray-500">API Key</dt>
            <dd class="text-gray-300 font-mono text-xs">{config.api_key_masked}</dd>
          </div>
          <div>
            <dt class="text-xs text-gray-500">Database ID</dt>
            <dd class="text-gray-300 font-mono text-xs">{config.database_id}</dd>
          </div>
          <div class="col-span-2">
            <dt class="text-xs text-gray-500">마지막 동기화 (인스턴스)</dt>
            <dd class="text-gray-300">{formatDate(config.last_sync)}</dd>
          </div>
          {#if config.users_database_id}
            <div class="col-span-2">
              <dt class="text-xs text-gray-500">사용자 매핑 DB</dt>
              <dd class="text-gray-300 font-mono text-xs">{config.users_database_id}</dd>
            </div>
          {/if}
          {#if config.hypervisors_database_id}
            <div>
              <dt class="text-xs text-gray-500">하이퍼바이저 DB</dt>
              <dd class="text-gray-300 font-mono text-xs">{config.hypervisors_database_id}</dd>
            </div>
            <div>
              <dt class="text-xs text-gray-500">마지막 동기화 (하이퍼바이저)</dt>
              <dd class="text-gray-300">{formatDate(config.hypervisors_last_sync)}</dd>
            </div>
          {/if}
        </dl>

        <div class="flex gap-2 mt-4">
          <button
            onclick={testSync}
            disabled={testing}
            class="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors"
          >
            {testing ? '동기화 중...' : '지금 동기화'}
          </button>
          <button
            onclick={deleteConfig}
            disabled={deleting}
            class="px-4 py-2 text-red-400 hover:text-red-300 border border-red-900 hover:border-red-700 text-sm rounded-lg transition-colors"
          >
            설정 삭제
          </button>
        </div>
        {#if testMessage}
          <div class="mt-2 text-green-400 text-sm">{testMessage}</div>
        {/if}
        {#if testError}
          <div class="mt-2 text-red-400 text-sm">{testError}</div>
        {/if}
      </div>
    {/if}

    <!-- 설정 폼 -->
    <div class="bg-gray-900 border border-gray-800 rounded-lg p-5">
      <h2 class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-4">
        {config?.configured ? '설정 수정' : '새 설정'}
      </h2>

      <div class="space-y-4">
        <div>
          <label class="block text-xs text-gray-400 mb-1.5">
            Notion API Key (Internal Integration Token)
            <input
              bind:value={apiKey}
              type="password"
              placeholder={config?.configured ? '변경 시에만 입력' : 'ntn_...'}
              class="w-full mt-1.5 bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 font-mono"
            />
          </label>
          <p class="text-xs text-gray-600 mt-1">
            <a href="https://www.notion.so/profile/integrations" target="_blank" class="text-blue-500 hover:text-blue-400">Notion Integrations</a>에서 생성한 Internal Integration의 Secret
          </p>
        </div>

        <div>
          <label class="block text-xs text-gray-400 mb-1.5">
            인스턴스 Database ID <span class="text-red-400">*</span>
            <input
              bind:value={databaseId}
              type="text"
              placeholder="32자리 UUID (URL에서 복사)"
              class="w-full mt-1.5 bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 font-mono"
            />
          </label>
          <p class="text-xs text-gray-600 mt-1">
            Notion DB URL: notion.so/&lt;workspace&gt;/<strong>&lt;database_id&gt;</strong>?v=... — Integration에 DB 접근 권한을 부여해야 합니다
          </p>
        </div>

        <div>
          <label class="block text-xs text-gray-400 mb-1.5">
            사용자 매핑 Database ID <span class="text-gray-600">(선택)</span>
            <input
              bind:value={usersDatabaseId}
              type="text"
              placeholder="People DB의 이메일로 사용자 이름 매핑"
              class="w-full mt-1.5 bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 font-mono"
            />
          </label>
          <p class="text-xs text-gray-600 mt-1">조회 전용 — 이메일 필드로 OpenStack 사용자와 매핑, 인스턴스 DB에 실명 표시</p>
        </div>

        <div>
          <label class="block text-xs text-gray-400 mb-1.5">
            하이퍼바이저 Database ID <span class="text-gray-600">(선택)</span>
            <input
              bind:value={hypervisorsDatabaseId}
              type="text"
              placeholder="호스트별 CPU/RAM 사용량 동기화"
              class="w-full mt-1.5 bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 font-mono"
            />
          </label>
          <p class="text-xs text-gray-600 mt-1">호스트명, 상태, VM 수, vCPU, RAM 사용량을 주기적으로 동기화</p>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-xs text-gray-400 mb-1.5">
              동기화 간격 (분)
              <input
                bind:value={intervalMinutes}
                type="number"
                min="1"
                max="1440"
                class="w-full mt-1.5 bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
              />
            </label>
          </div>
          <div class="flex items-end pb-2">
            <label class="flex items-center gap-2 cursor-pointer">
              <input
                bind:checked={enabled}
                type="checkbox"
                class="w-4 h-4 rounded border-gray-600 bg-gray-800 text-blue-600 focus:ring-blue-500"
              />
              <span class="text-sm text-gray-300">활성화</span>
            </label>
          </div>
        </div>
      </div>

      {#if saveError}
        <div class="mt-3 text-red-400 text-sm">{saveError}</div>
      {/if}
      {#if saveMessage}
        <div class="mt-3 text-green-400 text-sm">{saveMessage}</div>
      {/if}

      <div class="mt-5">
        <button
          onclick={saveConfig}
          disabled={saving}
          class="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors"
        >
          {saving ? '저장 중...' : '연결 검증 및 저장'}
        </button>
      </div>
    </div>

    <!-- 안내 -->
    <div class="mt-6 bg-gray-900/50 border border-gray-800 rounded-lg p-5">
      <h3 class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">설정 방법</h3>
      <ol class="text-xs text-gray-500 space-y-1.5 list-decimal list-inside">
        <li>
          <a href="https://www.notion.so/profile/integrations" target="_blank" class="text-blue-500 hover:text-blue-400">Notion Integrations</a>에서 Internal Integration 생성
        </li>
        <li>Notion에서 빈 Database 페이지 생성</li>
        <li>Database 우측 상단 ... 메뉴 → "연결 추가" → 생성한 Integration 선택</li>
        <li>Database URL에서 ID 복사 (32자리 영숫자)</li>
        <li>위 폼에 API Key와 Database ID 입력 후 저장 → 필요한 컬럼이 자동 생성됩니다</li>
      </ol>
    </div>
  {/if}
</div>
