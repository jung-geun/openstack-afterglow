<script lang="ts">
  import { onMount } from 'svelte';
  import { auth } from '$lib/stores/auth';
  import { api, ApiError } from '$lib/api/client';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';

  interface Keypair {
    name: string;
    fingerprint: string;
    type: string;
    public_key?: string;
    private_key?: string;
  }

  let keypairs = $state<Keypair[]>([]);
  let loading = $state(true);
  let error = $state('');
  let deleting = $state<string | null>(null);
  let showModal = $state(false);
  let creating = $state(false);
  let createError = $state('');
  let createdPrivateKey = $state<string | null>(null);
  let form = $state({ name: '', public_key: '' });

  async function fetchKeypairs() {
    try {
      keypairs = await api.get<Keypair[]>('/api/keypairs', $auth.token ?? undefined, $auth.projectId ?? undefined);
      error = '';
    } catch (e) {
      error = e instanceof ApiError ? `조회 실패 (${e.status})` : '서버 오류';
    } finally {
      loading = false;
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

  function handleFileUpload(event: Event) {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      form.public_key = ((e.target?.result as string) ?? '').trim();
    };
    reader.readAsText(file);
    // 같은 파일 재선택 허용
    input.value = '';
  }

  onMount(fetchKeypairs);
</script>

{#if showModal}
  <div class="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onclick={() => showModal = false} role="dialog" aria-modal="true" tabindex="-1" onkeydown={(e) => e.key === 'Escape' && (showModal = false)}>
    <div class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl" onclick={(e) => e.stopPropagation()} role="document" onkeydown={(e) => e.stopPropagation()}>
      {#if createdPrivateKey}
        <h2 class="text-lg font-semibold text-white mb-3">개인키 다운로드</h2>
        <p class="text-sm text-yellow-300 mb-3">이 키는 다시 표시되지 않습니다. 지금 저장하세요.</p>
        <pre class="bg-gray-800 rounded p-3 text-xs text-green-300 overflow-auto max-h-48 mb-4">{createdPrivateKey}</pre>
        <button onclick={() => { createdPrivateKey = null; showModal = false; }} class="w-full px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-colors">확인</button>
      {:else}
        <h2 class="text-lg font-semibold text-white mb-5">키페어 생성</h2>
        <div class="space-y-4">
          <div>
            <label class="block text-xs text-gray-400 mb-1.5 uppercase tracking-wide">이름</label>
            <input bind:value={form.name} type="text" placeholder="my-keypair" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500" />
          </div>
          <div>
            <div class="flex items-center justify-between mb-1.5">
              <label class="text-xs text-gray-400 uppercase tracking-wide">공개키 (선택 - 비우면 자동 생성)</label>
              <label class="text-xs text-blue-400 hover:text-blue-300 cursor-pointer transition-colors">
                파일 선택
                <input type="file" accept=".pub,.pem,.txt" class="hidden" onchange={handleFileUpload} />
              </label>
            </div>
            <textarea bind:value={form.public_key} placeholder="ssh-rsa AAAA..." rows="3" class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 font-mono resize-none"></textarea>
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

<div class="p-8">
  <div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold text-white">키페어</h1>
    <button onclick={() => showModal = true} class="bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">+ 키페어 생성</button>
  </div>

  {#if error}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>{/if}

  {#if loading}
    <LoadingSkeleton variant="table" rows={4} />
  {:else if keypairs.length === 0}
    <div class="text-center py-20 text-gray-600">
      <div class="text-5xl mb-4">🔑</div>
      <p class="text-lg">키페어가 없습니다</p>
    </div>
  {:else}
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
            <th class="text-left py-3 pr-6">이름</th>
            <th class="text-left py-3 pr-6">지문 (Fingerprint)</th>
            <th class="text-left py-3 pr-6">타입</th>
            <th class="text-right py-3">액션</th>
          </tr>
        </thead>
        <tbody>
          {#each keypairs as kp (kp.name)}
            <tr class="border-b border-gray-800/50">
              <td class="py-3 pr-6 font-medium text-white">{kp.name}</td>
              <td class="py-3 pr-6 text-gray-400 text-xs font-mono">{kp.fingerprint}</td>
              <td class="py-3 pr-6"><span class="px-1.5 py-0.5 bg-gray-800 text-gray-300 rounded text-xs">{kp.type}</span></td>
              <td class="py-3 text-right">
                <button onclick={() => deleteKeypair(kp.name)} disabled={deleting === kp.name} class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-1 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors">
                  {deleting === kp.name ? '삭제 중...' : '삭제'}
                </button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>
