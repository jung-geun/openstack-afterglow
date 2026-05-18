<script lang="ts">
	import type { Instance } from '$lib/types/resources';
	import StatusChip from '$lib/components/ui/StatusChip.svelte';

	let {
		instances,
		loading,
	}: {
		instances: Instance[];
		loading: boolean;
	} = $props();

	function getFirstIp(inst: Instance): string {
		return inst.ip_addresses?.[0]?.addr ?? '—';
	}
</script>

<div class="bg-gray-900 border border-gray-800 rounded-2xl p-5">
	<div class="flex items-center mb-3.5">
		<div class="text-white text-[15px] font-semibold">최근 인스턴스</div>
		<a href="/dashboard/compute/instances" class="ml-auto text-[13px] text-gray-500 hover:text-gray-200 transition-colors">모두 보기 →</a>
	</div>
	{#if loading && instances.length === 0}
		<div class="space-y-2">
			{#each Array(4) as _}
				<div class="h-10 bg-gray-800 rounded animate-pulse"></div>
			{/each}
		</div>
	{:else if instances.length === 0}
		<div class="text-gray-600 text-sm py-6 text-center">인스턴스가 없습니다</div>
	{:else}
		<div class="overflow-x-auto">
			<div class="min-w-[360px]">
				<div class="grid grid-cols-[1.7fr_100px_130px_0px] sm:grid-cols-[1.7fr_110px_130px_120px] px-3.5 py-2 bg-[#0B1220] rounded-t-[10px] border border-gray-800 border-b-0 text-[11px] uppercase tracking-wider text-gray-500 font-medium">
					<div>NAME</div>
					<div>STATUS</div>
					<div>IP</div>
					<div class="hidden sm:block">FLAVOR</div>
				</div>
				<div class="border border-gray-800 rounded-b-[10px] overflow-hidden">
					{#each instances as inst, i}
						<a href="/dashboard/compute/instances"
							class="grid grid-cols-[1.7fr_100px_130px_0px] sm:grid-cols-[1.7fr_110px_130px_120px] px-3.5 py-2.5 text-[13px] items-center hover:bg-gray-800/30 transition-colors {i < instances.length - 1 ? 'border-b border-gray-800' : ''}">
							<div class="text-white font-medium truncate">{inst.name}</div>
							<div><StatusChip status={inst.status} /></div>
							<div class="text-gray-300 font-mono text-xs">{getFirstIp(inst)}</div>
							<div class="text-gray-400 text-xs truncate hidden sm:block">{inst.flavor_name ?? '—'}</div>
						</a>
					{/each}
				</div>
			</div>
		</div>
	{/if}
</div>
