<script lang="ts">
	import { formatNumber } from '$lib/utils/format';
	import type { Overview } from '$lib/types/adminOverview';

	let { overview }: { overview: Overview } = $props();
</script>

<div class="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
	<!-- 하이퍼바이저 -->
	<div class="bg-gray-900 border border-gray-800 rounded-2xl p-[18px] flex items-center gap-3.5">
		<div class="w-10 h-10 rounded-[10px] shrink-0 border flex items-center justify-center bg-blue-500/15 border-blue-500/30 text-blue-400">
			<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2"/></svg>
		</div>
		<div class="flex-1 min-w-0">
			<div class="text-[11px] uppercase tracking-wider font-medium text-gray-500">하이퍼바이저</div>
			<div class="flex items-baseline gap-2 mt-0.5">
				<div class="text-[28px] font-bold text-white leading-none">{formatNumber(overview.hypervisor_count)}</div>
				<a href="/admin/hypervisors" class="ml-auto text-[11px] text-blue-400 hover:text-blue-300 transition-colors">상세 →</a>
			</div>
		</div>
	</div>

	<!-- 총 VM -->
	<div class="bg-gray-900 border border-gray-800 rounded-2xl p-[18px] flex items-center gap-3.5">
		<div class="w-10 h-10 rounded-[10px] shrink-0 border flex items-center justify-center bg-emerald-500/15 border-emerald-500/30 text-emerald-400">
			<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18"/></svg>
		</div>
		<div class="flex-1 min-w-0">
			<div class="text-[11px] uppercase tracking-wider font-medium text-gray-500">총 VM</div>
			<div class="flex items-baseline gap-2 mt-0.5 flex-wrap">
				<div class="text-[28px] font-bold text-white leading-none">{formatNumber(overview.running_vms)}</div>
				{#if overview.instance_stats}
					<div class="flex gap-2 text-[11px] ml-auto flex-wrap">
						<span class="text-emerald-400">● {overview.instance_stats.active}</span>
						<span class="text-red-400">● {overview.instance_stats.error} err</span>
					</div>
				{/if}
			</div>
			<a href="/admin/instances" class="text-[11px] text-blue-400 hover:text-blue-300 transition-colors">전체 보기 →</a>
		</div>
	</div>

	<!-- GPU VM -->
	<div class="bg-gray-900 border border-gray-800 rounded-2xl p-[18px] flex items-center gap-3.5">
		<div class="w-10 h-10 rounded-[10px] shrink-0 border flex items-center justify-center bg-violet-500/15 border-violet-500/30 text-violet-400">
			<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg>
		</div>
		<div class="flex-1 min-w-0">
			<div class="text-[11px] uppercase tracking-wider font-medium text-gray-500">GPU VM</div>
			<div class="flex items-baseline gap-2 mt-0.5">
				<div class="text-[28px] font-bold {overview.gpu_instances > 0 ? 'text-violet-300' : 'text-white'} leading-none">{formatNumber(overview.gpu_instances)}</div>
				<div class="text-gray-500 text-xs">인스턴스</div>
			</div>
		</div>
	</div>
</div>
