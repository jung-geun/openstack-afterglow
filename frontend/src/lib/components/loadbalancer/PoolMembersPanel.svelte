<script lang="ts">
  import { useLoadbalancerDetailController } from '$lib/stores/loadbalancerDetailController.svelte';
  import Button from '$lib/components/ui/Button.svelte';

  interface Props {
    poolId: string;
  }
  // poolId는 부모가 selectedPoolId === pool.id 분기에서 마운트할 때 식별용으로 전달
  // 실제 API 호출은 store의 selectedPoolId를 사용
  let { poolId: _poolId }: Props = $props();
  void _poolId;

  const s = useLoadbalancerDetailController();
</script>

<div class="mt-2 ml-4 bg-gray-800/30 rounded-lg p-4 border border-gray-700">
  <div class="flex items-center justify-between mb-3">
    <span class="text-sm text-gray-400">멤버 ({s.selectedPoolMembers.length})</span>
    <button
      onclick={() => s.toggleAddMember()}
      class="text-blue-400 hover:text-blue-300 text-xs px-2 py-1 rounded border border-blue-900 hover:border-blue-700 transition-colors"
    >+ 멤버 추가</button>
  </div>

  {#if s.showAddMember}
    <div class="mb-3 grid grid-cols-1 @lg/panel:grid-cols-2 gap-2">
      <input
        bind:value={s.memberForm.address}
        placeholder="IP 주소"
        class="bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200"
      />
      <input
        bind:value={s.memberForm.protocol_port}
        type="number"
        min="1"
        max="65535"
        placeholder="포트"
        class="bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200"
      />
      <input
        bind:value={s.memberForm.weight}
        type="number"
        min="1"
        max="256"
        placeholder="가중치"
        class="bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200"
      />
      <Button onclick={() => s.addMember()} disabled={s.saving || !s.memberForm.address} size="sm">추가</Button>
      <button onclick={() => s.toggleAddMember()} class="text-gray-400 hover:text-gray-200 text-sm px-2 text-center rounded border border-gray-700">취소</button>
    </div>
  {/if}

  {#if s.selectedPoolMembers.length === 0}
    <p class="text-xs text-gray-600">멤버가 없습니다.</p>
  {:else}
    <div class="space-y-1.5">
      {#each s.selectedPoolMembers as member}
        <div class="flex items-center justify-between bg-gray-800/50 rounded px-3 py-2">
          <div class="text-xs">
            <span class="text-white font-mono">{member.address}:{member.protocol_port}</span>
            <span class="ml-2 text-gray-500">가중치 {member.weight}</span>
            <span class="ml-2 {member.status === 'ACTIVE' ? 'text-green-400' : 'text-yellow-400'}">{member.status}</span>
          </div>
          <button onclick={() => s.removeMember(member.id)} disabled={s.saving} class="text-red-400 hover:text-red-300 text-xs">제거</button>
        </div>
      {/each}
    </div>
  {/if}
</div>
