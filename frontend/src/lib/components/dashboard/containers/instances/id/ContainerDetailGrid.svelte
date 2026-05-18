<script lang="ts">
  import type { ZunContainerDetail } from '$lib/types/zunContainer';
  import { containerDetailStatusColor } from '$lib/types/zunContainer';

  interface Props {
    container: ZunContainerDetail;
  }

  let { container }: Props = $props();
</script>

<div class="grid grid-cols-2 gap-4 mb-6">
  <div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
    <div class="text-xs text-gray-500 mb-1">상태</div>
    <span class="px-2 py-0.5 rounded text-xs font-medium {containerDetailStatusColor[container.status] ?? 'text-gray-400 bg-gray-800'}">{container.status}</span>
    {#if container.status_reason}
      <p class="text-xs text-gray-500 mt-2">{container.status_reason}</p>
    {/if}
  </div>
  <div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
    <div class="text-xs text-gray-500 mb-1">이미지</div>
    <div class="text-white text-xs font-mono">{container.image ?? '-'}</div>
  </div>
  <div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
    <div class="text-xs text-gray-500 mb-1">리소스</div>
    <div class="text-white text-sm">CPU {container.cpu ?? '-'} / MEM {container.memory ?? '-'} MB</div>
  </div>
  <div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
    <div class="text-xs text-gray-500 mb-1">생성일</div>
    <div class="text-white text-sm">{container.created_at?.slice(0, 19).replace('T', ' ') ?? '-'}</div>
  </div>
</div>

{#if container.command}
  <div class="bg-gray-900 border border-gray-800 rounded-xl p-4 mb-4">
    <div class="text-xs text-gray-500 mb-2">명령</div>
    <pre class="text-green-300 text-xs font-mono">{container.command}</pre>
  </div>
{/if}
