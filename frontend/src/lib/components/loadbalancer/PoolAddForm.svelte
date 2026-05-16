<script lang="ts">
  import { useLoadBalancerDetail } from '$lib/stores/loadBalancerDetail.svelte';
  import Button from '$lib/components/ui/Button.svelte';

  const s = useLoadBalancerDetail();
</script>

{#if s.showAddPool}
  <div class="mb-4 p-4 bg-gray-800/60 border border-gray-700 rounded-lg grid grid-cols-1 @lg/panel:grid-cols-3 gap-2">
    <input
      bind:value={s.poolForm.name}
      placeholder="이름 (선택)"
      class="bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200"
    />
    <select
      bind:value={s.poolForm.protocol}
      class="bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200"
    >
      {#each ['HTTP', 'HTTPS', 'TCP', 'UDP'] as p}
        <option value={p}>{p}</option>
      {/each}
    </select>
    <select
      bind:value={s.poolForm.lb_algorithm}
      class="bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200"
    >
      {#each ['ROUND_ROBIN', 'LEAST_CONNECTIONS', 'SOURCE_IP'] as a}
        <option value={a}>{a}</option>
      {/each}
    </select>
    <Button onclick={() => s.createPool()} disabled={s.saving} class="col-span-2" size="sm">생성</Button>
    <button onclick={() => s.toggleAddPool()} class="text-gray-400 hover:text-gray-200 text-sm px-2 text-center">취소</button>
  </div>
{/if}
