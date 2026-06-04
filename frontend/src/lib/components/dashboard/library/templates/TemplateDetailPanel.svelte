<script lang="ts">
  import SlidePanel from '$lib/components/SlidePanel.svelte';
  import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
  import StatusChip from '$lib/components/ui/StatusChip.svelte';
  import type { TemplateInfo } from '$lib/types/templates';

  let {
    template,
    loading,
    onClose,
  }: {
    template: TemplateInfo | null;
    loading: boolean;
    onClose: () => void;
  } = $props();

  function formatDate(dt: string): string {
    return new Date(dt).toLocaleDateString('ko-KR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    });
  }
</script>

<SlidePanel {onClose}>
  {#if loading}
    <div class="p-6"><LoadingSkeleton rows={4} /></div>
  {:else if template}
    <div class="p-6">
      <h2 class="text-lg font-semibold mb-1">{template.name}</h2>
      <p class="text-sm text-gray-400 mb-5">버전 {template.version} · {template.ubuntu_base}</p>

      {#if template.note}
        <p class="text-sm text-gray-300 mb-5">{template.note}</p>
      {/if}

      <dl class="space-y-3 text-sm mb-6">
        <div>
          <dt class="text-gray-500 text-xs">Leaf Layer ID</dt>
          <dd class="font-mono text-xs text-gray-300 break-all mt-0.5">{template.leaf_layer_id}</dd>
        </div>
        <div>
          <dt class="text-gray-500 text-xs">생성자</dt>
          <dd class="text-gray-300 mt-0.5">{template.created_by}</dd>
        </div>
        <div>
          <dt class="text-gray-500 text-xs">생성일</dt>
          <dd class="text-gray-300 mt-0.5">{formatDate(template.created_at)}</dd>
        </div>
      </dl>

      {#if template.resolved_stack && template.resolved_stack.length > 0}
        <div>
          <h3 class="text-sm font-medium text-gray-300 mb-3">레이어 스택 (base → leaf)</h3>
          <div class="space-y-2">
            {#each template.resolved_stack as layer, i}
              <div class="flex items-center gap-3 p-2 rounded bg-gray-700/40">
                <div class="w-5 h-5 rounded-full bg-gray-600 flex items-center justify-center text-xs text-gray-300">{i + 1}</div>
                <div class="flex-1 min-w-0">
                  <div class="text-sm text-gray-200">{layer.name}</div>
                  <div class="text-xs text-gray-500">{layer.version}</div>
                </div>
                <StatusChip status={layer.sealed ? 'sealed' : 'draft'} />
              </div>
            {/each}
          </div>
        </div>
      {/if}

      <a
        href="/dashboard/library/{encodeURIComponent(template.leaf_layer_id)}"
        class="mt-5 inline-block text-sm text-blue-400 hover:text-blue-300"
      >Leaf 레이어 상세 →</a>
    </div>
  {/if}
</SlidePanel>
