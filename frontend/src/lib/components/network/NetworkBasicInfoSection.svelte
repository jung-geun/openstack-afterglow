<script lang="ts">
	import { useNetworkDetail } from '$lib/stores/networkDetail.svelte';

	const s = useNetworkDetail();
</script>

<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
	<h3 class="text-xs text-gray-500 uppercase tracking-wide mb-3">기본 정보</h3>
	<dl class="space-y-2 text-xs">
		<div class="flex justify-between">
			<dt class="text-gray-400">ID</dt>
			<dd class="text-gray-300 font-mono text-xs break-all">{s.network!.id}</dd>
		</div>
		<div class="flex justify-between">
			<dt class="text-gray-400">상태</dt>
			<dd class="{s.network!.status === 'ACTIVE' ? 'text-green-400' : 'text-gray-400'}">{s.network!.status}</dd>
		</div>
		<div class="flex justify-between">
			<dt class="text-gray-400">유형</dt>
			<dd class="flex gap-1">
				{#if s.network!.is_external}<span class="px-1.5 py-0.5 bg-orange-900/30 text-orange-300 rounded text-xs">외부</span>{/if}
				{#if s.network!.is_shared}<span class="px-1.5 py-0.5 bg-blue-900/30 text-blue-300 rounded text-xs">공유</span>{/if}
				{#if !s.network!.is_external && !s.network!.is_shared}<span class="text-gray-500">내부</span>{/if}
			</dd>
		</div>
	</dl>
</div>
