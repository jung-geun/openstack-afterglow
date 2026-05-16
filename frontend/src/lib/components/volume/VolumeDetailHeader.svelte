<script lang="ts">
  import { useVolumeDetail } from '$lib/stores/volumeDetail.svelte';
  import DetailHeader from '$lib/components/ui/DetailHeader.svelte';
  import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';

  interface Props {
    ar: { active: boolean; intervalSeconds: number; intervalOptions: number[] };
    onClose?: () => void;
  }
  let { ar = $bindable(), onClose }: Props = $props();

  const s = useVolumeDetail();
</script>

<DetailHeader title={s.volume?.name || 'Volume'} status={s.volume?.status ?? null}>
  {#snippet actions()}
    <AutoRefreshControl
      bind:active={ar.active}
      bind:intervalSeconds={ar.intervalSeconds}
      intervalOptions={ar.intervalOptions}
      refreshing={s.loading}
      onManualRefresh={() => s.loadAll()}
    />
    <button onclick={onClose} class="text-gray-400 hover:text-white transition-colors text-lg leading-none">✕</button>
  {/snippet}
</DetailHeader>
