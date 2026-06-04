<script lang="ts">
  import Button from '$lib/components/ui/Button.svelte';
  import GitLabLoginButton from './GitLabLoginButton.svelte';

  let {
    domainName = $bindable(),
    username = $bindable(),
    password = $bindable(),
    error,
    loading,
    gitlabEnabled,
    gitlabLoading,
    onSubmit,
    onGitlab,
  }: {
    domainName: string;
    username: string;
    password: string;
    error: string;
    loading: boolean;
    gitlabEnabled: boolean;
    gitlabLoading: boolean;
    onSubmit: () => Promise<void>;
    onGitlab: () => Promise<void>;
  } = $props();
</script>

<form
  onsubmit={(e) => { e.preventDefault(); onSubmit(); }}
  class="bg-gray-900 rounded-xl border border-gray-700 p-8 space-y-4"
>
  {#if error}
    <div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">
      {error}
    </div>
  {/if}

  <div>
    <label for="domain" class="block text-gray-400 text-xs mb-1.5 uppercase tracking-wide">도메인</label>
    <input
      id="domain"
      bind:value={domainName}
      type="text"
      class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
    />
  </div>

  <div>
    <label for="username" class="block text-gray-400 text-xs mb-1.5 uppercase tracking-wide">사용자명</label>
    <input
      id="username"
      bind:value={username}
      type="text"
      required
      class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
    />
  </div>

  <div>
    <label for="password" class="block text-gray-400 text-xs mb-1.5 uppercase tracking-wide">비밀번호</label>
    <input
      id="password"
      bind:value={password}
      type="password"
      required
      onkeydown={(e) => { if (e.key === 'Enter' && !loading) { e.preventDefault(); onSubmit(); } }}
      class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
    />
  </div>

  <Button type="submit" disabled={loading} class="w-full" size="lg">
    {loading ? '로그인 중...' : '로그인'}
  </Button>

  <GitLabLoginButton enabled={gitlabEnabled} loading={gitlabLoading} onClick={onGitlab} />
</form>
