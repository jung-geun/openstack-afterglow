<script lang="ts">
	import type { Member } from '$lib/types/loadbalancer';

	let {
		members,
		membersLoading,
		adding,
		error,
		onAdd,
		onRemove,
	}: {
		members: Member[];
		membersLoading: boolean;
		adding: boolean;
		error: string;
		onAdd: (form: { address: string; protocol_port: number; weight: number; name: string }) => Promise<boolean>;
		onRemove: (memberId: string) => Promise<void>;
	} = $props();

	let showAddMember = $state(false);
	let memberForm = $state({ address: '', protocol_port: 80, weight: 1, name: '' });

	async function handleAdd() {
		const ok = await onAdd(memberForm);
		if (ok) {
			showAddMember = false;
			memberForm = { address: '', protocol_port: 80, weight: 1, name: '' };
		}
	}
</script>

<div class="mt-2 ml-4 bg-gray-800/30 rounded-lg p-4 border border-gray-700">
	<div class="flex items-center justify-between mb-3">
		<span class="text-sm text-gray-400">멤버 ({members.length})</span>
		<button onclick={() => showAddMember = !showAddMember} class="text-blue-400 hover:text-blue-300 text-xs px-2 py-1 rounded border border-blue-900 hover:border-blue-700 transition-colors">+ 멤버 추가</button>
	</div>

	{#if showAddMember}
		<div class="mb-3 grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-2">
			<input bind:value={memberForm.address} placeholder="IP 주소" class="bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 col-span-2" />
			<input bind:value={memberForm.protocol_port} type="number" min="1" max="65535" placeholder="포트" class="bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200" />
			<input bind:value={memberForm.weight} type="number" min="1" max="256" placeholder="가중치" class="bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200" />
			<button onclick={handleAdd} disabled={adding || !memberForm.address} class="col-span-3 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 text-white text-sm px-3 py-2 rounded">추가</button>
			<button onclick={() => showAddMember = false} class="text-gray-400 hover:text-gray-200 text-sm px-2 text-center rounded border border-gray-700">취소</button>
		</div>
	{/if}

	{#if members.length === 0}
		<p class="text-xs text-gray-600">멤버가 없습니다.</p>
	{:else}
		<div class="space-y-1.5">
			{#each members as member}
				<div class="flex items-center justify-between bg-gray-800/50 rounded px-3 py-2">
					<div class="text-xs">
						<span class="text-white font-mono">{member.address}:{member.protocol_port}</span>
						<span class="ml-2 text-gray-500">가중치 {member.weight}</span>
						<span class="ml-2 {member.status === 'ACTIVE' ? 'text-green-400' : 'text-yellow-400'}">{member.status}</span>
					</div>
					<button onclick={() => onRemove(member.id)} disabled={adding} class="text-red-400 hover:text-red-300 text-xs">제거</button>
				</div>
			{/each}
		</div>
	{/if}
</div>
