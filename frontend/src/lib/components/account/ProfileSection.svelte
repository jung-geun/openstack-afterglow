<script lang="ts">
  import { auth } from '$lib/stores/auth';
  import { api, ApiError } from '$lib/api/client';

  interface Profile {
    id: string;
    name: string;
    email: string;
    description: string;
  }

  const token = $derived($auth.token ?? undefined);
  const projectId = $derived($auth.projectId ?? undefined);

  let profile = $state<Profile>({ id: '', name: '', email: '', description: '' });
  let loading = $state(true);
  let saving = $state(false);
  let error = $state('');
  let success = $state('');

  let editName = $state('');
  let editEmail = $state('');
  let editDescription = $state('');

  async function load() {
    loading = true;
    error = '';
    try {
      const res = await api.get<Profile>('/api/v1/profile', token, projectId);
      profile = res;
      editName = res.name;
      editEmail = res.email;
      editDescription = res.description;
    } catch (e) {
      error = e instanceof ApiError ? e.message : '프로필을 불러올 수 없습니다';
    } finally {
      loading = false;
    }
  }

  async function save() {
    error = '';
    success = '';
    saving = true;
    try {
      const body: Record<string, string> = {};
      if (editName !== profile.name) body.name = editName;
      if (editEmail !== profile.email) body.email = editEmail;
      if (editDescription !== profile.description) body.description = editDescription;
      if (Object.keys(body).length === 0) {
        error = '변경된 내용이 없습니다';
        return;
      }
      const res = await api.patch<Profile>('/api/v1/profile', body, token, projectId);
      profile = res;
      success = '프로필이 저장되었습니다';
    } catch (e) {
      error = e instanceof ApiError ? e.message : '저장 실패';
    } finally {
      saving = false;
    }
  }

  $effect(() => {
    if ($auth.token) load();
  });
</script>

<div class="bg-gray-900 border border-gray-800 rounded-xl p-5">
  <h3 class="text-sm font-semibold text-white mb-4">프로필 정보</h3>

  {#if error}
    <div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-3 py-2 text-xs mb-3">{error}</div>
  {/if}
  {#if success}
    <div class="bg-green-900/40 border border-green-700 text-green-300 rounded-lg px-3 py-2 text-xs mb-3">{success}</div>
  {/if}

  {#if loading}
    <div class="space-y-2">
      {#each [1, 2, 3] as _}
        <div class="h-9 bg-gray-800 rounded animate-pulse"></div>
      {/each}
    </div>
  {:else}
    <div class="space-y-3">
      <div>
        <label class="block text-xs text-gray-400 mb-1">사용자 ID</label>
        <div class="text-sm text-gray-500 font-mono bg-gray-800/50 rounded px-3 py-2">{profile.id}</div>
      </div>
      <div>
        <label class="block text-xs text-gray-400 mb-1">이름 (닉네임)</label>
        <input
          type="text"
          bind:value={editName}
          class="w-full bg-gray-800 border border-gray-700 focus:border-blue-500 text-white text-sm rounded-lg px-3 py-2 outline-none transition-colors"
          placeholder="이름 입력"
        />
      </div>
      <div>
        <label class="block text-xs text-gray-400 mb-1">이메일</label>
        <input
          type="email"
          bind:value={editEmail}
          class="w-full bg-gray-800 border border-gray-700 focus:border-blue-500 text-white text-sm rounded-lg px-3 py-2 outline-none transition-colors"
          placeholder="이메일 입력"
        />
      </div>
      <div>
        <label class="block text-xs text-gray-400 mb-1">설명</label>
        <textarea
          bind:value={editDescription}
          rows="2"
          class="w-full bg-gray-800 border border-gray-700 focus:border-blue-500 text-white text-sm rounded-lg px-3 py-2 outline-none transition-colors resize-none"
          placeholder="설명 입력 (선택)"
        ></textarea>
      </div>
    </div>
    <div class="mt-4 flex justify-end">
      <button
        onclick={save}
        disabled={saving}
        class="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm rounded-lg transition-colors"
      >{saving ? '저장 중...' : '저장'}</button>
    </div>
  {/if}
</div>
