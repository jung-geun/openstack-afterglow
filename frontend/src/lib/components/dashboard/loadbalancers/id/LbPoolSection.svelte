<script lang="ts">
	import type { Pool, Member } from '$lib/types/resources';
	import LbPoolMembersPanel from './LbPoolMembersPanel.svelte';

	let {
		pools,
		selectedPoolId,
		members,
		membersLoading,
		saving,
		error,
		addingMember,
		addMemberError,
		onAddPool,
		onDeletePool,
		onSelectPool,
		onAddMember,
		onRemoveMember,
	}: {
		pools: Pool[];
		selectedPoolId: string | null;
		members: Member[];
		membersLoading: boolean;
		saving: boolean;
		error: string;
		addingMember: boolean;
		addMemberError: string;
		onAddPool: (form: { protocol: string; lb_algorithm: string; name: string }) => Promise<boolean>;
		onDeletePool: (id: string) => Promise<void>;
		onSelectPool: (id: string | null) => void;
		onAddMember: (form: { address: string; protocol_port: number; weight: number; name: string }) => Promise<boolean>;
		onRemoveMember: (memberId: string) => Promise<void>;
	} = $props();

	let showAddPool = $state(false);
	let poolForm = $state({ protocol: 'HTTP', lb_algorithm: 'ROUND_ROBIN', name: '' });

	async function handleAddPool() {
		const ok = await onAddPool(poolForm);
		if (ok) {
			showAddPool = false;
			poolForm = { protocol: 'HTTP', lb_algorithm: 'ROUND_ROBIN', name: '' };
		}
	}
</script>

<section class="bg-gray-900 border border-gray-800 rounded-lg p-5 mb-4">
	<div class="flex items-center justify-between mb-4">
		<h2 class="font-semibold text-white">풀 ({pools.length})</h2>
		<button onclick={() => showAddPool = !showAddPool} class="text-blue-400 hover:text-blue-300 text-xs px-2 py-1 rounded border border-blue-900 hover:border-blue-700 transition-colors">+ 추가</button>
	</div>

	{#if showAddPool}
		<div class="mb-4 p-4 bg-gray-800/60 border border-gray-700 rounded-lg grid grid-cols-1 sm:grid-cols-3 gap-2">
			<input bind:value={poolForm.name} placeholder="이름 (선택)" class="bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200" />
			<select bind:value={poolForm.protocol} class="bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200">
				{#each ['HTTP', 'HTTPS', 'TCP', 'UDP'] as p}
					<option value={p}>{p}</option>
				{/each}
			</select>
			<select bind:value={poolForm.lb_algorithm} class="bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200">
				{#each ['ROUND_ROBIN', 'LEAST_CONNECTIONS', 'SOURCE_IP'] as a}
					<option value={a}>{a}</option>
				{/each}
			</select>
			<button onclick={handleAddPool} disabled={saving} class="col-span-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 text-white text-sm px-3 py-2 rounded">생성</button>
			<button onclick={() => showAddPool = false} class="text-gray-400 hover:text-gray-200 text-sm px-2 text-center">취소</button>
		</div>
	{/if}

	{#if pools.length === 0}
		<p class="text-sm text-gray-600">풀이 없습니다.</p>
	{:else}
		<div class="space-y-2">
			{#each pools as pool}
				<div>
					<div
						onclick={() => onSelectPool(selectedPoolId === pool.id ? null : pool.id)}
						onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && onSelectPool(selectedPoolId === pool.id ? null : pool.id)}
						role="button"
						tabindex="0"
						class="flex items-center justify-between bg-gray-800/50 hover:bg-gray-800 rounded-lg px-4 py-3 cursor-pointer transition-colors {selectedPoolId === pool.id ? 'border border-blue-800' : ''}"
					>
						<div class="text-sm">
							<span class="text-white font-medium">{pool.name || pool.id.slice(0, 10)}</span>
							<span class="ml-2 text-xs text-purple-300 bg-purple-900/30 px-1.5 py-0.5 rounded">{pool.protocol}</span>
							<span class="ml-2 text-xs text-gray-500">{pool.lb_algorithm}</span>
							<span class="ml-2 text-xs {pool.status === 'ACTIVE' ? 'text-green-400' : 'text-yellow-400'}">{pool.status}</span>
						</div>
						<div class="flex gap-2">
							<span class="text-xs text-gray-500">{selectedPoolId === pool.id ? '▲ 멤버 접기' : '▼ 멤버 보기'}</span>
							<button onclick={(e) => { e.stopPropagation(); onDeletePool(pool.id); }} disabled={saving} class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-1 rounded border border-red-900 hover:border-red-700 transition-colors">삭제</button>
						</div>
					</div>

					{#if selectedPoolId === pool.id}
						<LbPoolMembersPanel
							{members}
							{membersLoading}
							adding={addingMember}
							error={addMemberError}
							onAdd={onAddMember}
							onRemove={onRemoveMember}
						/>
					{/if}
				</div>
			{/each}
		</div>
	{/if}
</section>
