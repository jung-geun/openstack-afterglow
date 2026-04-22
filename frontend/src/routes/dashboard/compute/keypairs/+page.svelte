<script lang="ts">
  import { auth } from '$lib/stores/auth';
  import { untrack } from 'svelte';
  import { api, ApiError } from '$lib/api/client';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
  import RefreshButton from '$lib/components/RefreshButton.svelte';
  import AutoRefreshToggle from '$lib/components/AutoRefreshToggle.svelte';
  import PageHeader from '$lib/components/ui/PageHeader.svelte';

  interface Keypair {
    name: string;
    fingerprint: string;
    type: string;
    public_key?: string;
    private_key?: string;
  }

  let keypairs = $state<Keypair[]>([]);
  let loading = $state(true);
  let refreshing = $state(false);
  let error = $state('');
  let autoRefresh = $state(false);
  let deleting = $state<string | null>(null);
  let copiedFingerprint = $state<string | null>(null);
  let showModal = $state(false);
  let creating = $state(false);
  let createError = $state('');
  let createdPrivateKey = $state<string | null>(null);
  let form = $state({ name: '', public_key: '' });

  async function fetchKeypairs(opts?: { refresh?: boolean }) {
    try {
      keypairs = await api.get<Keypair[]>('/api/keypairs', $auth.token ?? undefined, $auth.projectId ?? undefined, opts);
      error = '';
    } catch (e) {
      error = e instanceof ApiError ? `조회 실패 (${e.status})` : '서버 오류';
    } finally {
      loading = false;
    }
  }

  async function forceRefresh() {
    refreshing = true;
    try {
      await fetchKeypairs({ refresh: true });
    } finally {
      refreshing = false;
    }
  }

  async function createKeypair() {
    if (!form.name.trim()) return;
    creating = true;
    createError = '';
    try {
      const result = await api.post<Keypair>('/api/keypairs', {
        name: form.name,
        public_key: form.public_key.trim() || null,
      }, $auth.token ?? undefined, $auth.projectId ?? undefined);
      if (result.private_key) {
        createdPrivateKey = result.private_key;
      } else {
        showModal = false;
      }
      form = { name: '', public_key: '' };
      await fetchKeypairs();
    } catch (e) {
      createError = e instanceof ApiError ? e.message : '생성 실패';
    } finally {
      creating = false;
    }
  }

  async function deleteKeypair(name: string) {
    if (!confirm(`키페어 "${name}"을 삭제하시겠습니까?`)) return;
    deleting = name;
    try {
      await api.delete(`/api/keypairs/${name}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
      await fetchKeypairs();
    } catch (e) {
      alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
    } finally {
      deleting = null;
    }
  }

  async function copyFingerprint(fingerprint: string) {
    try {
      await navigator.clipboard.writeText(fingerprint);
      copiedFingerprint = fingerprint;
      setTimeout(() => (copiedFingerprint = null), 2000);
    } catch {
      // 비보안 컨텍스트(HTTP) 또는 권한 거부 시 조용히 무시
    }
  }

  function handleFileUpload(event: Event) {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    // 최대 64KB — SSH 공개키는 일반적으로 1KB 미만
    if (file.size > 65536) {
      createError = '파일이 너무 큽니다 (최대 64KB)';
      input.value = '';
      return;
    }
    const reader = new FileReader();
    reader.onload = (e) => {
      const content = ((e.target?.result as string) ?? '').trim();
      if (content && !/^(ssh-rsa|ssh-ed25519|ssh-dss|ecdsa-sha2-\S+)\s/.test(content)) {
        createError = '유효한 SSH 공개키 형식이 아닙니다 (ssh-rsa, ssh-ed25519 등)';
        return;
      }
      form.public_key = content;
    };
    reader.readAsText(file);
    // 같은 파일 재선택 허용
    input.value = '';
  }

  $effect(() => {
    const pid = $auth.projectId;
    if (!pid) return;
    untrack(() => { fetchKeypairs(); });
  });

  $effect(() => {
    if (!$auth.projectId || !autoRefresh) return;
    const interval = setInterval(() => untrack(() => { fetchKeypairs(); }), 60000);
    return () => clearInterval(interval);
  });
</script>

{#if showModal}
  <div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onclick={() => showModal = false} role="dialog" aria-modal="true" tabindex="-1" onkeydown={(e) => e.key === 'Escape' && (showModal = false)}>
    <div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()} role="none" onkeydown={(e) => e.stopPropagation()}>
      {#if createdPrivateKey}
        <h2 class="text-lg font-semibold text-white mb-3">개인키 다운로드</h2>
        <p class="text-sm text-yellow-300 mb-3">이 키는 다시 표시되지 않습니다. 지금 저장하세요.</p>
        <pre class="bg-gray-800 rounded p-3 text-xs text-green-300 overflow-auto max-h-48 mb-4">{createdPrivateKey}</pre>
        <button onclick={() => { createdPrivateKey = null; showModal = false; }} class="w-full px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-colors">확인</button>
      {:else}
        <h2 class="text-lg font-semibold text-white mb-5">키페어 생성</h2>
        <div class="space-y-4">
          <div>
            <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름
              <input bind:value={form.name} type="text" placeholder="my-keypair" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1.5" />
            </label>
          </div>
          <div>
            <div class="flex items-center justify-between mb-1.5">
              <label for="keypair-pubkey" class="text-xs text-gray-400 uppercase tracking-wide">공개키 (선택 - 비우면 자동 생성)</label>
              <label class="text-xs text-blue-400 hover:text-blue-300 cursor-pointer transition-colors">
                파일 선택
                <input type="file" accept=".pub,.pem,.txt" class="hidden" onchange={handleFileUpload} />
              </label>
            </div>
            <textarea id="keypair-pubkey" bind:value={form.public_key} placeholder="ssh-rsa AAAA..." rows="3" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 font-mono resize-none"></textarea>
          </div>
        </div>
        {#if createError}<div class="mt-3 text-red-400 text-xs">{createError}</div>{/if}
        <div class="flex justify-end gap-3 mt-6">
          <button onclick={() => showModal = false} class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">취소</button>
          <button onclick={createKeypair} disabled={creating} class="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors">{creating ? '생성 중...' : '생성'}</button>
        </div>
      {/if}
    </div>
  </div>
{/if}

<div class="p-4 md:p-8">
  <PageHeader breadcrumb="COMPUTE / KEYPAIRS" title="키페어">
    {#snippet actions()}
      <AutoRefreshToggle bind:active={autoRefresh} intervalSeconds={60} />
      <RefreshButton {refreshing} onclick={forceRefresh} />
      <button onclick={() => showModal = true} class="bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">+ 키페어 생성</button>
    {/snippet}
  </PageHeader>

  {#if error}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>{/if}

  {#if loading}
    <LoadingSkeleton variant="table" rows={4} />
  {:else if keypairs.length === 0}
    <div class="text-center py-20 text-gray-600">
      <div class="text-5xl mb-4">🔑</div>
      <p class="text-lg">키페어가 없습니다</p>
    </div>
  {:else}
    <div class="bg-[#0B1220] border border-gray-800 rounded-[10px] overflow-hidden">
      <!-- 헤더 -->
      <div class="grid grid-cols-[1.2fr_140px_2fr_120px] px-4 py-2.5 border-b border-gray-800 text-[11px] uppercase tracking-wider text-gray-500 font-medium">
        <div>이름</div>
        <div>유형</div>
        <div>지문</div>
        <div class="text-right">액션</div>
      </div>
      {#each keypairs as kp, i (kp.name)}
        <div class="grid grid-cols-[1.2fr_140px_2fr_120px] px-4 py-3 text-[13px] items-center {i < keypairs.length - 1 ? 'border-b border-gray-800' : ''} hover:bg-gray-800/30 transition-colors">
          <!-- 이름 -->
          <div class="text-white font-medium flex items-center gap-2.5 min-w-0">
            <svg class="w-4 h-4 text-violet-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
            <span class="truncate">{kp.name}</span>
          </div>
          <!-- 유형 -->
          <div>
            <span class="text-[11px] font-mono px-2 py-0.5 rounded-md bg-violet-900/25 border border-violet-800 text-violet-400">{kp.type}</span>
          </div>
          <!-- 지문 -->
          <div class="text-gray-400 font-mono text-[11px] truncate">{kp.fingerprint}</div>
          <!-- 액션 -->
          <div class="flex gap-1.5 justify-end">
            <button
              onclick={() => copyFingerprint(kp.fingerprint)}
              class="text-xs px-2 py-1 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-200 border border-gray-700 transition-colors"
            >{copiedFingerprint === kp.fingerprint ? '복사됨' : '복사'}</button>
            <button
              onclick={() => deleteKeypair(kp.name)}
              disabled={deleting === kp.name}
              class="text-xs px-2 py-1 rounded-lg bg-transparent hover:bg-red-950/40 text-red-400 border border-red-900 disabled:text-gray-600 disabled:border-gray-700 transition-colors"
            >{deleting === kp.name ? '삭제 중...' : '삭제'}</button>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>
