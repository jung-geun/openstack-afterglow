<script lang="ts">
  import StatusChip from '$lib/components/ui/StatusChip.svelte';
  import type { LayerInfo } from '$lib/types/layer';
  import { layerHref } from '$lib/types/layer';

  interface Props {
    dependents: LayerInfo[];
  }

  let { dependents }: Props = $props();
</script>

<div class="bg-gray-800 rounded-lg border border-gray-700 p-5">
  <h3 class="text-sm font-medium text-gray-300 mb-4">파생 레이어 ({dependents.length})</h3>
  {#if dependents.length === 0}
    <p class="text-sm text-gray-500">파생된 레이어 없음</p>
  {:else}
    <div class="space-y-2">
      {#each dependents as dep}
        <a
          href={layerHref(dep.id)}
          class="flex items-center justify-between p-2 rounded bg-gray-700/40 hover:bg-gray-700 transition-colors"
        >
          <div>
            <div class="text-sm text-gray-200">{dep.name}</div>
            <div class="text-xs text-gray-500">{dep.version}</div>
          </div>
          <StatusChip status={dep.sealed ? 'sealed' : 'draft'} />
        </a>
      {/each}
    </div>
  {/if}
</div>
