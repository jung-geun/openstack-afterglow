<script lang="ts">
  import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
  import type { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';

  interface Props {
    logs: string;
    logsLoading: boolean;
    ar: ReturnType<typeof createAutoRefresh>;
    onManualRefresh: () => void;
  }

  let { logs, logsLoading, ar, onManualRefresh }: Props = $props();
</script>

<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
  <div class="flex items-center justify-between mb-3">
    <div class="text-xs text-gray-500">로그</div>
    <AutoRefreshControl
      bind:active={ar.active}
      bind:intervalSeconds={ar.intervalSeconds}
      intervalOptions={ar.intervalOptions}
      refreshing={logsLoading}
      onManualRefresh={onManualRefresh}
    />
  </div>
  {#if logs}
    <pre class="bg-gray-950 rounded p-3 text-xs text-gray-300 overflow-auto max-h-64 font-mono whitespace-pre-wrap">{logs}</pre>
  {:else}
    <div class="text-gray-600 text-xs">로그 새로고침 버튼을 클릭하세요</div>
  {/if}
</div>
