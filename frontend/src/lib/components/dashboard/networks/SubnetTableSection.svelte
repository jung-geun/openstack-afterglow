<script lang="ts">
	import type { NetworkDetail } from '$lib/types/networks';

	let {
		network,
		onAdd,
		onSave,
		onDelete,
		addingSubnet,
		savingSubnet,
		addError,
		saveError,
		onClearAddError,
		onClearSaveError,
	}: {
		network: NetworkDetail;
		onAdd: (form: { name: string; cidr: string; gateway: string; dhcp: boolean }) => Promise<boolean>;
		onSave: (subnetId: string, form: { name: string; gateway: string; dhcp: boolean }) => Promise<boolean>;
		onDelete: (subnetId: string, subnetName: string) => Promise<void>;
		addingSubnet: boolean;
		savingSubnet: boolean;
		addError: string;
		saveError: string;
		onClearAddError: () => void;
		onClearSaveError: () => void;
	} = $props();

	let showSubnetForm = $state(false);
	let subnetForm = $state({ name: '', cidr: '10.0.0.0/24', gateway: '', dhcp: true });
	let editingSubnetId = $state<string | null>(null);
	let editSubnetForm = $state({ name: '', gateway: '', dhcp: true });

	function startEditSubnet(subnet: { id: string; name: string; gateway_ip: string | null; dhcp_enabled: boolean }) {
		editingSubnetId = subnet.id;
		editSubnetForm = {
			name: subnet.name || '',
			gateway: subnet.gateway_ip ?? '',
			dhcp: subnet.dhcp_enabled,
		};
		onClearSaveError();
	}

	async function handleAdd() {
		const ok = await onAdd(subnetForm);
		if (ok) {
			showSubnetForm = false;
			onClearAddError();
			subnetForm = { name: '', cidr: '10.0.0.0/24', gateway: '', dhcp: true };
		}
	}

	async function handleSave() {
		if (!editingSubnetId) return;
		const ok = await onSave(editingSubnetId, editSubnetForm);
		if (ok) editingSubnetId = null;
	}
</script>

<div class="bg-gray-900 border border-gray-800 rounded-lg p-6 mb-4">
	<div class="flex items-center justify-between mb-4">
		<h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide">서브넷</h2>
		{#if !network.is_external}
			<button
				onclick={() => { showSubnetForm = !showSubnetForm; onClearAddError(); }}
				class="text-xs text-blue-400 hover:text-blue-300 transition-colors"
			>
				{showSubnetForm ? '닫기' : '+ 서브넷 추가'}
			</button>
		{/if}
	</div>

	{#if showSubnetForm}
		<div class="mb-4 bg-gray-800 rounded-lg p-4 space-y-3">
			<div class="grid grid-cols-2 gap-3">
				<div>
					<label class="block text-xs text-gray-400 mb-1">이름 (선택)
						<input
							bind:value={subnetForm.name}
							type="text"
							placeholder="my-subnet"
							class="w-full bg-gray-700 border border-gray-600 rounded px-2.5 py-1.5 text-white text-sm focus:outline-none focus:border-blue-500 mt-1"
						/>
					</label>
				</div>
				<div>
					<label class="block text-xs text-gray-400 mb-1">CIDR
						<input
							bind:value={subnetForm.cidr}
							type="text"
							placeholder="10.0.0.0/24"
							class="w-full bg-gray-700 border border-gray-600 rounded px-2.5 py-1.5 text-white text-sm font-mono focus:outline-none focus:border-blue-500 mt-1"
						/>
					</label>
				</div>
				<div>
					<label class="block text-xs text-gray-400 mb-1">게이트웨이 (선택)
						<input
							bind:value={subnetForm.gateway}
							type="text"
							placeholder="10.0.0.1"
							class="w-full bg-gray-700 border border-gray-600 rounded px-2.5 py-1.5 text-white text-sm font-mono focus:outline-none focus:border-blue-500 mt-1"
						/>
					</label>
				</div>
				<div class="flex items-end pb-1.5">
					<label class="flex items-center gap-2 text-sm text-gray-300">
						<input type="checkbox" bind:checked={subnetForm.dhcp} class="rounded border-gray-600" />
						DHCP 활성화
					</label>
				</div>
			</div>
			{#if addError}
				<p class="text-red-400 text-xs">{addError}</p>
			{/if}
			<div class="flex justify-end">
				<button
					onclick={handleAdd}
					disabled={addingSubnet}
					class="text-sm px-4 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 text-white rounded transition-colors"
				>
					{addingSubnet ? '추가 중...' : '서브넷 추가'}
				</button>
			</div>
		</div>
	{/if}

	{#if network.subnet_details.length > 0}
		<table class="w-full text-sm">
			<thead>
				<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
					<th class="text-left py-2 pr-6">이름</th>
					<th class="text-left py-2 pr-6">CIDR</th>
					<th class="text-left py-2 pr-6">게이트웨이</th>
					<th class="text-left py-2 pr-4">DHCP</th>
					{#if !network.is_external}
						<th class="text-right py-2">액션</th>
					{/if}
				</tr>
			</thead>
			<tbody>
				{#each network.subnet_details as subnet}
					<tr class="border-b border-gray-800/50">
						{#if editingSubnetId === subnet.id}
							<td colspan={network.is_external ? 4 : 5} class="py-3">
								<div class="bg-gray-800 rounded-lg p-4 space-y-3">
									<div class="grid grid-cols-2 gap-3">
										<div>
											<label class="block text-xs text-gray-400 mb-1">이름
												<input
													bind:value={editSubnetForm.name}
													type="text"
													class="w-full bg-gray-700 border border-gray-600 rounded px-2.5 py-1.5 text-white text-sm focus:outline-none focus:border-blue-500 mt-1"
												/>
											</label>
										</div>
										<div>
											<label class="block text-xs text-gray-400 mb-1">게이트웨이
												<input
													bind:value={editSubnetForm.gateway}
													type="text"
													placeholder={subnet.gateway_ip ?? '없음'}
													class="w-full bg-gray-700 border border-gray-600 rounded px-2.5 py-1.5 text-white text-sm font-mono focus:outline-none focus:border-blue-500 mt-1"
												/>
											</label>
										</div>
										<div class="flex items-center">
											<label class="flex items-center gap-2 text-sm text-gray-300">
												<input type="checkbox" bind:checked={editSubnetForm.dhcp} class="rounded border-gray-600" />
												DHCP 활성화
											</label>
										</div>
									</div>
									{#if saveError}
										<p class="text-red-400 text-xs">{saveError}</p>
									{/if}
									<div class="flex justify-end gap-2">
										<button
											onclick={() => { editingSubnetId = null; }}
											class="text-xs text-gray-400 hover:text-gray-200 px-3 py-1.5 transition-colors"
										>취소</button>
										<button
											onclick={handleSave}
											disabled={savingSubnet}
											class="text-xs px-4 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 text-white rounded transition-colors"
										>{savingSubnet ? '저장 중...' : '저장'}</button>
									</div>
								</div>
							</td>
						{:else}
							<td class="py-2 pr-6 text-gray-300"><span class="max-md:block max-md:max-w-[66vw] max-md:truncate" title={subnet.name || subnet.id}>{subnet.name || '-'}</span></td>
							<td class="py-2 pr-6 text-gray-300 font-mono text-xs">{subnet.cidr}</td>
							<td class="py-2 pr-6 text-gray-400 font-mono text-xs">{subnet.gateway_ip ?? '-'}</td>
							<td class="py-2 pr-4">
								{#if subnet.dhcp_enabled}
									<span class="px-1.5 py-0.5 bg-green-900/30 text-green-400 rounded text-xs">활성</span>
								{:else}
									<span class="text-gray-600 text-xs">-</span>
								{/if}
							</td>
							{#if !network.is_external}
								<td class="py-2 text-right">
									<div class="flex items-center justify-end gap-1">
										<button
											onclick={() => startEditSubnet(subnet)}
											class="text-xs text-blue-400 hover:text-blue-300 px-2 py-1 border border-blue-900 hover:border-blue-700 rounded transition-colors"
										>편집</button>
										<button
											onclick={() => onDelete(subnet.id, subnet.name)}
											class="text-xs text-red-400 hover:text-red-300 px-2 py-1 border border-red-900 hover:border-red-700 rounded transition-colors"
										>삭제</button>
									</div>
								</td>
							{/if}
						{/if}
					</tr>
				{/each}
			</tbody>
		</table>
	{:else}
		<p class="text-sm text-gray-500">서브넷 없음</p>
	{/if}
</div>
