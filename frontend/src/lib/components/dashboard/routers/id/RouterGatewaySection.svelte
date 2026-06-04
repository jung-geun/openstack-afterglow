<script lang="ts">
	import type { RouterDetail } from '$lib/types/router';
	import type { Network } from '$lib/types/networks';

	let {
		router,
		externalNetworks,
		saving,
		onSet,
		onRemove,
	}: {
		router: RouterDetail;
		externalNetworks: Network[];
		saving: boolean;
		onSet: (externalNetworkId: string) => Promise<boolean>;
		onRemove: () => Promise<void>;
	} = $props();

	let showSetGateway = $state(false);
	let selectedExtNetId = $state('');

	async function handleSet() {
		const ok = await onSet(selectedExtNetId);
		if (ok) {
			showSetGateway = false;
			selectedExtNetId = '';
		}
	}
</script>

<section class="bg-gray-900 border border-gray-800 rounded-lg p-5 mb-4">
	<div class="flex items-center justify-between mb-4">
		<h2 class="font-semibold text-white">외부 게이트웨이</h2>
		<div class="flex gap-2">
			{#if router.external_gateway_network_id}
				<button
					onclick={onRemove}
					disabled={saving}
					class="text-red-400 hover:text-red-300 text-xs px-2 py-1 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors"
				>게이트웨이 제거</button>
			{:else}
				<button
					onclick={() => showSetGateway = !showSetGateway}
					class="text-blue-400 hover:text-blue-300 text-xs px-2 py-1 rounded border border-blue-900 hover:border-blue-700 transition-colors"
				>게이트웨이 설정</button>
			{/if}
		</div>
	</div>

	{#if router.external_gateway_network_id}
		<div class="text-sm">
			<span class="text-gray-400">네트워크: </span>
			<span class="text-orange-300">{router.external_gateway_network_name || router.external_gateway_network_id}</span>
		</div>
	{:else}
		<p class="text-sm text-gray-600">외부 게이트웨이가 설정되지 않았습니다.</p>
	{/if}

	{#if showSetGateway}
		<div class="mt-4 flex gap-2">
			<select bind:value={selectedExtNetId} class="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200">
				<option value="">외부 네트워크 선택</option>
				{#each externalNetworks as net}
					<option value={net.id}>{net.name || net.id.slice(0, 12)}</option>
				{/each}
			</select>
			<button
				onclick={handleSet}
				disabled={!selectedExtNetId || saving}
				class="bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 text-white text-sm px-3 py-2 rounded transition-colors"
			>설정</button>
			<button onclick={() => showSetGateway = false} class="text-gray-400 hover:text-gray-200 text-sm px-2">취소</button>
		</div>
	{/if}
</section>
