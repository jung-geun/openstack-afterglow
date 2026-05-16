<script lang="ts">
	import Button from '$lib/components/ui/Button.svelte';
	import { useRouterDetail } from '$lib/stores/routerDetail.svelte';

	const s = useRouterDetail();
</script>

<section class="bg-gray-900 border border-gray-800 rounded-lg p-5 mb-4">
	<div class="flex items-center justify-between mb-3">
		<h4 class="font-semibold text-white text-sm">외부 게이트웨이</h4>
		<div class="flex gap-2">
			{#if s.router!.external_gateway_network_id}
				<button
					onclick={() => s.removeGateway()}
					disabled={s.saving}
					class="text-red-400 hover:text-red-300 text-xs px-2 py-1 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors"
				>게이트웨이 제거</button>
			{:else}
				<button
					onclick={() => s.showSetGateway = !s.showSetGateway}
					class="text-blue-400 hover:text-blue-300 text-xs px-2 py-1 rounded border border-blue-900 hover:border-blue-700 transition-colors"
				>게이트웨이 설정</button>
			{/if}
		</div>
	</div>

	{#if s.router!.external_gateway_network_id}
		<div class="text-sm">
			<span class="text-gray-400">네트워크: </span>
			<span class="text-orange-300">{s.router!.external_gateway_network_name || s.router!.external_gateway_network_id}</span>
		</div>
	{:else}
		<p class="text-sm text-gray-600">외부 게이트웨이가 설정되지 않았습니다.</p>
	{/if}

	{#if s.showSetGateway}
		<div class="mt-4 flex gap-2">
			<select bind:value={s.selectedExtNetId} class="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200">
				<option value="">외부 네트워크 선택</option>
				{#each s.externalNetworks as net}
					<option value={net.id}>{net.name || net.id.slice(0, 12)}</option>
				{/each}
			</select>
			<Button onclick={() => s.setGateway()} disabled={!s.selectedExtNetId || s.saving} size="sm">설정</Button>
			<button onclick={() => s.showSetGateway = false} class="text-gray-400 hover:text-gray-200 text-sm px-2">취소</button>
		</div>
	{/if}
</section>
