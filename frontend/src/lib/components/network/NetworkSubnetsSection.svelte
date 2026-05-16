<script lang="ts">
	import { useNetworkDetail } from '$lib/stores/networkDetail.svelte';

	const s = useNetworkDetail();
</script>

{#if s.network!.subnet_details.length > 0}
	<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
		<h3 class="text-xs text-gray-500 uppercase tracking-wide mb-3">서브넷 ({s.network!.subnet_details.length})</h3>
		<div class="space-y-3">
			{#each s.network!.subnet_details as subnet}
				<div class="border-b border-gray-800/50 pb-2 last:border-0 last:pb-0">
					<div class="text-xs text-white font-medium">{subnet.name || subnet.id.slice(0, 8)}</div>
					<dl class="mt-1 space-y-1 text-xs">
						<div class="flex justify-between">
							<dt class="text-gray-500">CIDR</dt>
							<dd class="text-gray-300 font-mono">{subnet.cidr}</dd>
						</div>
						<div class="flex justify-between">
							<dt class="text-gray-500">게이트웨이</dt>
							<dd class="text-gray-300 font-mono">{subnet.gateway_ip || '-'}</dd>
						</div>
						<div class="flex justify-between">
							<dt class="text-gray-500">DHCP</dt>
							<dd class="{subnet.dhcp_enabled ? 'text-green-400' : 'text-gray-500'}">{subnet.dhcp_enabled ? '활성' : '비활성'}</dd>
						</div>
					</dl>
				</div>
			{/each}
		</div>
	</div>
{:else}
	<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
		<h3 class="text-xs text-gray-500 uppercase tracking-wide mb-2">서브넷</h3>
		<p class="text-xs text-gray-600">서브넷이 없습니다</p>
	</div>
{/if}
