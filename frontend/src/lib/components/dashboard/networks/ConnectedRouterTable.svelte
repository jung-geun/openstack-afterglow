<script lang="ts">
	import type { NetworkRouterInfo } from '$lib/types/resources';

	let { routers }: { routers: NetworkRouterInfo[] } = $props();
</script>

<div class="bg-gray-900 border border-gray-800 rounded-lg p-6">
	<h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-4">연결된 라우터</h2>
	<table class="w-full text-sm">
		<thead>
			<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
				<th class="text-left py-2 pr-6">이름</th>
				<th class="text-left py-2 pr-6">외부 게이트웨이</th>
				<th class="text-left py-2">연결된 서브넷</th>
			</tr>
		</thead>
		<tbody>
			{#each routers as router}
				<tr class="border-b border-gray-800/50">
					<td class="py-2 pr-6 text-gray-300">{router.name || router.id.slice(0, 12) + '…'}</td>
					<td class="py-2 pr-6">
						{#if router.external_gateway_network_id}
							<span class="text-orange-300 text-xs font-mono">{router.external_gateway_network_id.slice(0, 12)}…</span>
						{:else}
							<span class="text-gray-600 text-xs">-</span>
						{/if}
					</td>
					<td class="py-2 text-gray-500 text-xs">
						{router.connected_subnet_ids.length}개
					</td>
				</tr>
			{/each}
		</tbody>
	</table>
</div>
