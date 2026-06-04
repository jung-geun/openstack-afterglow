<script lang="ts">
	import type { ProjectUsage } from '$lib/types/adminOverview';
	import { usageBar, usageGrad, formatQuota } from '$lib/utils/usageBar';

	let {
		projects,
		loading,
		onSelectProject,
	}: {
		projects: ProjectUsage[];
		loading: boolean;
		onSelectProject: (p: ProjectUsage) => void;
	} = $props();
</script>

<div class="bg-gray-900 border border-gray-800 rounded-2xl p-5">
	<div class="text-white text-[15px] font-semibold mb-3.5">프로젝트별 리소스</div>
	{#if loading}
		<div class="space-y-2">
			{#each Array(4) as _}
				<div class="h-9 bg-gray-800 rounded animate-pulse"></div>
			{/each}
		</div>
	{:else if projects.length > 0}
		<!-- 테이블 헤더 -->
		<div class="grid grid-cols-[2fr_80px_120px_120px_120px_50px] px-3.5 py-2 bg-[#0B1220] rounded-t-[10px] border border-gray-800 border-b-0 text-[11px] uppercase tracking-wider text-gray-500 font-medium">
			<div>프로젝트</div><div class="text-right">VM</div><div>CPU</div><div>RAM</div><div>Disk</div><div class="text-right">GPU</div>
		</div>
		<div class="border border-gray-800 rounded-b-[10px] overflow-hidden">
			{#each projects.filter(p => p.instances.used > 0 || p.cpu.used > 0 || p.disk_gb.used > 0) as p, i}
				<button
					class="w-full grid grid-cols-[2fr_80px_120px_120px_120px_50px] px-3.5 py-2.5 text-[13px] items-center hover:bg-gray-800/30 transition-colors text-left {i < projects.filter(p => p.instances.used > 0 || p.cpu.used > 0 || p.disk_gb.used > 0).length - 1 ? 'border-b border-gray-800' : ''}"
					onclick={() => { onSelectProject(p); }}
				>
					<div>
						<span class="text-white font-medium">{p.project_name}</span>
						<span class="text-gray-600 text-xs ml-1">{p.project_id.slice(0, 8)}</span>
					</div>
					<div class="text-right text-gray-300 font-mono text-xs">{formatQuota(p.instances.used, p.instances.quota)}</div>
					<div class="flex items-center gap-1.5">
						<div class="w-14 h-1.5 bg-gray-700 rounded-full overflow-hidden shrink-0">
							<div class="h-full rounded-full transition-all" style="width: {usageBar(p.cpu.used, p.cpu.quota)}%; background: {usageGrad(p.cpu.used, p.cpu.quota)}"></div>
						</div>
						<span class="text-gray-400 font-mono text-[11px] min-w-[24px]">{p.cpu.used}</span>
					</div>
					<div class="flex items-center gap-1.5">
						<div class="w-14 h-1.5 bg-gray-700 rounded-full overflow-hidden shrink-0">
							<div class="h-full rounded-full transition-all" style="width: {usageBar(p.ram_mb.used, p.ram_mb.quota)}%; background: {usageGrad(p.ram_mb.used, p.ram_mb.quota)}"></div>
						</div>
						<span class="text-gray-400 font-mono text-[11px] min-w-[28px]">{Math.round(p.ram_mb.used/1024)}G</span>
					</div>
					<div class="flex items-center gap-1.5">
						<div class="w-14 h-1.5 bg-gray-700 rounded-full overflow-hidden shrink-0">
							<div class="h-full rounded-full transition-all" style="width: {usageBar(p.disk_gb.used, p.disk_gb.quota)}%; background: {usageGrad(p.disk_gb.used, p.disk_gb.quota)}"></div>
						</div>
						<span class="text-gray-400 font-mono text-[11px] min-w-[28px]">{Math.round(p.disk_gb.used)}G</span>
					</div>
					<div class="text-right">
						{#if p.gpu_instances > 0}
							<span class="text-violet-400 font-mono text-xs">{p.gpu_instances}</span>
						{:else}
							<span class="text-gray-700 text-xs">—</span>
						{/if}
					</div>
				</button>
			{/each}
		</div>
	{:else}
		<div class="text-gray-600 text-sm py-6 text-center">데이터가 없습니다</div>
	{/if}
</div>
