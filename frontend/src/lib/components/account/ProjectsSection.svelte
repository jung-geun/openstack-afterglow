<script lang="ts">
  import { auth } from '$lib/stores/auth';
  import { api, ApiError } from '$lib/api/client';

  interface Project {
    id: string;
    name: string;
    description?: string;
    enabled?: boolean;
  }

  const token = $derived($auth.token ?? undefined);

  let projects = $state<Project[]>([]);
  let loading = $state(true);
  let error = $state('');

  async function load() {
    loading = true;
    error = '';
    try {
      projects = await api.get<Project[]>('/api/auth/projects', token);
    } catch (e) {
      error = e instanceof ApiError ? e.message : '조회 실패';
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    if ($auth.token) load();
  });
</script>

<div class="bg-gray-900 border border-gray-800 rounded-xl p-5">
  <h3 class="text-sm font-semibold text-white mb-4">소속 프로젝트</h3>

  {#if error}
    <div class="text-red-400 text-xs">{error}</div>
  {:else if loading}
    <div class="space-y-2">
      {#each [1, 2] as _}
        <div class="h-8 bg-gray-800 rounded animate-pulse"></div>
      {/each}
    </div>
  {:else if projects.length === 0}
    <div class="text-gray-500 text-xs text-center py-4">소속 프로젝트가 없습니다</div>
  {:else}
    <div class="space-y-2">
      {#each projects as proj (proj.id)}
        {@const isActive = $auth.projectId === proj.id}
        <div class="flex items-center gap-3 px-3 py-2.5 rounded-lg {isActive ? 'bg-blue-500/10 border border-blue-500/30' : 'bg-gray-800/50'}">
          <div class="flex-1 min-w-0">
            <div class="text-sm font-medium truncate {isActive ? 'text-blue-300' : 'text-white'}">{proj.name}</div>
            {#if proj.description}
              <div class="text-[11px] text-gray-500 truncate">{proj.description}</div>
            {/if}
          </div>
          {#if isActive}
            <span class="text-[10px] text-blue-400 font-medium px-1.5 py-0.5 rounded bg-blue-500/15 border border-blue-500/30 shrink-0">활성</span>
          {/if}
        </div>
      {/each}
    </div>
  {/if}
</div>
