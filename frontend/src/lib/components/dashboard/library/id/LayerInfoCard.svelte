<script lang="ts">
  import StatusChip from '$lib/components/ui/StatusChip.svelte';
  import type { LayerInfo } from '$lib/types/layer';
  import { formatLayerSize, formatLayerDate } from '$lib/types/layer';

  interface Props {
    layer: LayerInfo;
    isAdmin: boolean;
    sealing: boolean;
    deleting: boolean;
    onSeal: () => Promise<void>;
    onDelete: () => Promise<void>;
  }

  let { layer, isAdmin, sealing, deleting, onSeal, onDelete }: Props = $props();

  let confirmDelete = $state(false);
</script>

<div class="bg-gray-800 rounded-lg border border-gray-700 p-5">
  <div class="flex items-center justify-between mb-4">
    <div>
      <h2 class="text-lg font-semibold">{layer.name}</h2>
      <p class="text-sm text-gray-400">버전: {layer.version}</p>
    </div>
    <StatusChip status={layer.sealed ? 'sealed' : 'draft'} />
  </div>
  <dl class="grid grid-cols-2 gap-3 text-sm">
    <div>
      <dt class="text-gray-500">Content Hash</dt>
      <dd class="font-mono text-xs text-gray-300 break-all mt-1">{layer.content_hash}</dd>
    </div>
    <div>
      <dt class="text-gray-500">Ubuntu Base</dt>
      <dd class="text-gray-300 mt-1">{layer.ubuntu_base ?? '-'}</dd>
    </div>
    <div>
      <dt class="text-gray-500">크기</dt>
      <dd class="text-gray-300 mt-1">{formatLayerSize(layer.size_bytes)}</dd>
    </div>
    <div>
      <dt class="text-gray-500">파일 수</dt>
      <dd class="text-gray-300 mt-1">{layer.file_count ?? '-'}</dd>
    </div>
    <div>
      <dt class="text-gray-500">생성일</dt>
      <dd class="text-gray-300 mt-1">{formatLayerDate(layer.created_at)}</dd>
    </div>
    <div>
      <dt class="text-gray-500">생성자</dt>
      <dd class="text-gray-300 mt-1">{layer.created_by}</dd>
    </div>
  </dl>

  <!-- 관리자 액션 -->
  {#if isAdmin}
    <div class="mt-5 pt-4 border-t border-gray-700 flex items-center gap-3">
      {#if !layer.sealed}
        <button
          onclick={onSeal}
          disabled={sealing}
          class="px-3 py-1.5 text-sm bg-amber-700 hover:bg-amber-600 disabled:opacity-50 rounded-md transition-colors"
        >
          {sealing ? '봉인 중...' : '🔒 봉인'}
        </button>
      {/if}
      {#if !confirmDelete}
        <button
          onclick={() => confirmDelete = true}
          class="px-3 py-1.5 text-sm bg-red-900/40 hover:bg-red-800/60 text-red-400 hover:text-red-300 border border-red-800 rounded-md transition-colors"
        >삭제</button>
      {:else}
        <span class="text-sm text-red-400">정말 삭제하시겠습니까?</span>
        <button
          onclick={onDelete}
          disabled={deleting}
          class="px-3 py-1.5 text-sm bg-red-700 hover:bg-red-600 disabled:opacity-50 rounded-md"
        >{deleting ? '삭제 중...' : '확인'}</button>
        <button
          onclick={() => confirmDelete = false}
          class="px-3 py-1.5 text-sm bg-gray-700 hover:bg-gray-600 rounded-md"
        >취소</button>
      {/if}
    </div>
  {/if}
</div>
