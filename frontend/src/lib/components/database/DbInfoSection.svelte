<script lang="ts">
	import { useDbInstanceDetail } from '$lib/stores/dbInstanceDetail.svelte';

	const s = useDbInstanceDetail();
</script>

<div class="bg-gray-900 border border-gray-800 rounded-xl p-4 grid grid-cols-1 @3xl/panel:grid-cols-2 gap-3 text-sm">
	<div class="col-span-2"><div class="text-gray-500 text-xs mb-0.5">ID</div><div class="text-gray-400 font-mono text-xs break-all">{s.instance!.id}</div></div>
	<div><div class="text-gray-500 text-xs mb-0.5">데이터스토어</div><div class="text-white">{s.instance!.datastore?.type ?? '-'} {s.instance!.datastore?.version ?? ''}</div></div>
	<div><div class="text-gray-500 text-xs mb-0.5">생성일</div><div class="text-white">{s.instance!.created_at ? s.instance!.created_at.slice(0, 10) : '-'}</div></div>
	<div>
		<div class="text-gray-500 text-xs mb-0.5">볼륨 크기</div>
		<div class="text-white">
			{s.instance!.size} GB
			{#if s.instance!.volume_used > 0}
				<span class="text-gray-500 text-xs ml-1">({s.instance!.volume_used} GB 사용)</span>
			{/if}
		</div>
	</div>
	<div>
		<div class="text-gray-500 text-xs mb-0.5">플레이버</div>
		<div class="text-white text-xs">{s.flavorDisplay}</div>
	</div>
	{#if s.instance!.address_map && Object.keys(s.instance!.address_map).length > 0}
		<div class="col-span-2">
			<div class="text-gray-500 text-xs mb-1">IP 주소</div>
			<div class="space-y-1">
				{#each Object.entries(s.instance!.address_map) as [netName, addrs]}
					<div class="flex flex-wrap items-center gap-2">
						<span class="text-gray-400 text-xs">{netName}:</span>
						{#each addrs as addr}
							<span class="text-white font-mono text-xs bg-gray-800 px-2 py-0.5 rounded">{addr}</span>
						{/each}
					</div>
				{/each}
			</div>
		</div>
	{:else if s.instance!.ips?.length > 0}
		<div class="col-span-2">
			<div class="text-gray-500 text-xs mb-1">IP 주소</div>
			<div class="flex flex-wrap gap-1.5">
				{#each s.instance!.ips as addr}
					<span class="text-white font-mono text-xs bg-gray-800 px-2 py-0.5 rounded">{addr}</span>
				{/each}
			</div>
		</div>
	{/if}
	{#if s.instance!.hostname}
		<div class="col-span-2"><div class="text-gray-500 text-xs mb-0.5">호스트명</div><div class="text-white font-mono text-xs">{s.instance!.hostname}</div></div>
	{/if}
</div>
