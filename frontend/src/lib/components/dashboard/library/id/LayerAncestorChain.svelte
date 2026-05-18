<script lang="ts">
  import StatusChip from '$lib/components/ui/StatusChip.svelte';
  import type { LayerInfo } from '$lib/types/layer';
  import { layerHref } from '$lib/types/layer';

  interface Props {
    ancestors: LayerInfo[];
    currentLayerId: string;
  }

  let { ancestors, currentLayerId }: Props = $props();
</script>

<div class="bg-gray-800 rounded-lg border border-gray-700 p-5">
  <h3 class="text-sm font-medium text-gray-300 mb-4">조상 체인 (base → leaf)</h3>
  {#if ancestors.length === 0}
    <p class="text-sm text-gray-500">최상위 레이어</p>
  {:else}
    <div class="relative">
      {#each ancestors as anc, i}
        <div class="flex items-center gap-2 py-2 {i < ancestors.length - 1 ? 'border-b border-gray-700' : ''}">
          <div class="flex flex-col items-center mr-2">
            <div class="w-2 h-2 rounded-full {anc.id === currentLayerId ? 'bg-blue-400' : 'bg-gray-600'}"></div>
            {#if i < ancestors.length - 1}
              <div class="w-0.5 h-4 bg-gray-700 mt-1"></div>
            {/if}
          </div>
          <div class="flex-1 min-w-0">
            {#if anc.id === currentLayerId}
              <div class="text-sm font-medium text-blue-400">{anc.name}</div>
              <div class="text-xs text-blue-400/60">{anc.version} · 현재</div>
            {:else}
              <a href={layerHref(anc.id)} class="text-sm text-gray-300 hover:text-white">{anc.name}</a>
              <div class="text-xs text-gray-500">{anc.version}</div>
            {/if}
          </div>
          <StatusChip status={anc.sealed ? 'sealed' : 'draft'} />
        </div>
      {/each}
    </div>
  {/if}
</div>
