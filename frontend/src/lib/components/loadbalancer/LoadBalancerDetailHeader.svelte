<script lang="ts">
  import { useLoadbalancerDetailController } from '$lib/stores/loadbalancerDetailController.svelte';
  import DetailHeader from '$lib/components/ui/DetailHeader.svelte';
  import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';

  interface Props {
    ar: { active: boolean; intervalSeconds: number; intervalOptions: number[] };
    onClose?: () => void;
  }
  let { ar = $bindable(), onClose }: Props = $props();

  const s = useLoadbalancerDetailController();
</script>

<div class="flex items-center justify-between mb-4">
  <button onclick={onClose} class="text-gray-400 hover:text-gray-200 text-sm transition-colors">← 목록으로</button>
  <AutoRefreshControl
    bind:active={ar.active}
    bind:intervalSeconds={ar.intervalSeconds}
    intervalOptions={ar.intervalOptions}
    refreshing={s.loading}
    onManualRefresh={() => s.fetchAll()}
  />
</div>

{#if s.lb}
  <DetailHeader
    title={s.lb.name || s.lb.id.slice(0, 12)}
    subtitle={s.lb.description}
    status={s.lb.status}
    secondaryStatus={s.lb.operating_status}
  >
    {#snippet meta()}
      {#if s.lb?.vip_address}
        <span class="text-xs text-gray-500 font-mono">VIP: {s.lb.vip_address}</span>
      {/if}
    {/snippet}
    {#snippet actions()}
      <button
        onclick={() => s.deleteLb()}
        disabled={s.saving}
        class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors"
      >삭제</button>
    {/snippet}
  </DetailHeader>
{/if}
