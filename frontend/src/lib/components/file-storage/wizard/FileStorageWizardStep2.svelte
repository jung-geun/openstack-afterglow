<script lang="ts">
	import { useFsWizard } from '$lib/stores/fileStorageWizardStore.svelte';

	const s = useFsWizard();
</script>

<h2 class="text-base font-semibold text-white mb-1">네트워크 설정</h2>
<p class="text-xs text-gray-500 mb-4">
	{s.fsForm.share_proto === 'NFS' ? 'NFS 프로토콜은 Share Network 선택이 필수입니다.' : 'CephFS는 Share Network 없이도 기본값으로 동작합니다.'}
</p>
<div class="space-y-4">
	<div>
		{#if s.fsForm.share_proto === 'CEPHFS'}
			<div class="bg-gray-800/40 border border-gray-700 rounded-lg px-3 py-2.5 text-xs text-gray-500">
				CephFS native 프로토콜은 Share Network 없이 직접 마운트됩니다.
			</div>
		{:else}
			<div class="flex items-center justify-between mb-1.5">
				<span class="text-xs text-gray-400 uppercase tracking-wide">Share Network {s.fsForm.share_proto === 'NFS' ? '*' : '(선택)'}</span>
				<button type="button" onclick={() => { s.showInlineNetCreate = !s.showInlineNetCreate; s.inlineNetError = ''; }}
					class="text-xs text-blue-400 hover:text-blue-300 transition-colors">
					{s.showInlineNetCreate ? '접기' : '+ 새로 생성'}
				</button>
			</div>
			{#if s.shareNetworks.length > 0}
				<select bind:value={s.selectedNetworkId} class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500">
					<option value="">기본값 사용{s.fsForm.share_proto === 'NFS' ? '' : ' (권장)'}</option>
					{#each s.shareNetworks as net}<option value={net.id}>{net.name || net.id.slice(0, 8)}{net.status ? ` (${net.status})` : ''}</option>{/each}
				</select>
			{:else if !s.showInlineNetCreate}
				<div class="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-500 text-sm">
					Share Network 없음 —
					<button onclick={() => (s.showInlineNetCreate = true)} class="text-blue-400 hover:text-blue-300 underline">지금 생성</button>
				</div>
			{/if}
		{/if}
	</div>

	{#if s.showInlineNetCreate}
		<div class="border border-gray-700 rounded-lg p-4 bg-gray-800/40 space-y-3">
			<p class="text-xs text-gray-400 font-medium uppercase tracking-wide">새 Share Network 생성</p>
			<div>
				<label class="block text-xs text-gray-500 mb-1">이름 *
					<input bind:value={s.inlineNetForm.name} type="text" placeholder="my-share-network"
						class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1" />
				</label>
			</div>
			<div>
				<label class="block text-xs text-gray-500 mb-1">설명 (선택)
					<input bind:value={s.inlineNetForm.description} type="text" placeholder="설명"
						class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1" />
				</label>
			</div>
			<div>
				<label class="block text-xs text-gray-500 mb-1">Neutron 네트워크 *
					<select bind:value={s.inlineNetForm.neutron_net_id} onchange={s.onInlineNetworkChange}
						class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1">
						<option value="">네트워크 선택</option>
						{#each s.neutronNetworks as net}<option value={net.id}>{net.name || net.id.slice(0, 12)} ({net.status})</option>{/each}
					</select>
				</label>
			</div>
			<div>
				<label class="block text-xs text-gray-500 mb-1">서브넷 *
					{#if s.loadingSubnets}
						<div class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-gray-500 text-sm mt-1">로딩 중...</div>
					{:else}
						<select bind:value={s.inlineNetForm.neutron_subnet_id} disabled={s.subnets.length === 0}
							class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500 mt-1 disabled:text-gray-600">
							<option value="">{s.subnets.length === 0 ? '네트워크를 먼저 선택하세요' : '서브넷 선택'}</option>
							{#each s.subnets as subnet}<option value={subnet.id}>{subnet.name || subnet.id.slice(0, 12)} {subnet.cidr ? `(${subnet.cidr})` : ''}</option>{/each}
						</select>
					{/if}
				</label>
			</div>
			{#if s.inlineNetError}<div class="text-red-400 text-xs bg-red-900/20 border border-red-800 rounded px-3 py-2">{s.inlineNetError}</div>{/if}
			<div class="flex justify-end gap-2">
				<button onclick={() => { s.showInlineNetCreate = false; s.inlineNetError = ''; }} class="px-3 py-1.5 text-xs text-gray-400 hover:text-white transition-colors">취소</button>
				<button onclick={s.createInlineNetwork} disabled={s.inlineNetCreating || !s.inlineNetForm.name.trim() || !s.inlineNetForm.neutron_net_id || !s.inlineNetForm.neutron_subnet_id}
					class="px-4 py-1.5 bg-blue-700 hover:bg-blue-600 disabled:bg-gray-700 disabled:text-gray-500 text-white text-xs font-medium rounded-lg transition-colors">
					{s.inlineNetCreating ? '생성 중...' : 'Share Network 생성'}
				</button>
			</div>
		</div>
	{/if}
</div>

{#if s.wizardError}<div class="mt-4 text-red-400 text-xs bg-red-900/20 border border-red-800 rounded px-3 py-2">{s.wizardError}</div>{/if}
<div class="flex justify-between gap-3 mt-6">
	<button onclick={s.backToStep1} class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">← 이전</button>
	<div class="flex gap-3">
		<button onclick={s.closeWizard} class="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors">취소</button>
		<button onclick={s.createFileStorage} disabled={s.creating}
			class="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors">
			{s.creating ? '생성 중...' : '생성'}
		</button>
	</div>
</div>
