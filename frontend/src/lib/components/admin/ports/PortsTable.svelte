<script lang="ts">
	import { projectNames } from '$lib/stores/projectNames';
	import type { PortInfo } from '$lib/types/networks';

	let {
		ports,
		markerStack,
		nextMarker,
		onEdit,
		onDelete,
		onPrev,
		onNext,
	}: {
		ports: PortInfo[];
		markerStack: string[];
		nextMarker: string | null;
		onEdit: (port: PortInfo) => void;
		onDelete: (port: PortInfo) => void;
		onPrev: () => void;
		onNext: () => void;
	} = $props();
</script>

<div class="overflow-x-auto">
	<table class="w-full text-sm">
		<thead>
			<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
				<th class="text-left py-2 pr-4">이름/ID</th>
				<th class="text-left py-2 pr-4">상태</th>
				<th class="text-left py-2 pr-4">Device Owner</th>
				<th class="text-left py-2 pr-4">IP 주소</th>
				<th class="text-left py-2 pr-4">프로젝트</th>
				<th class="text-left py-2">액션</th>
			</tr>
		</thead>
		<tbody>
			{#each ports as p (p.id)}
				<tr class="border-b border-gray-800/50 text-xs hover:bg-gray-800/30 transition-colors">
					<td class="py-2 pr-4">
						<div class="text-white">{p.name || '-'}</div>
						<div class="text-gray-600 font-mono">{p.id.slice(0, 12)}...</div>
					</td>
					<td class="py-2 pr-4 {p.status === 'ACTIVE' ? 'text-green-400' : 'text-gray-400'}">{p.status}</td>
					<td class="py-2 pr-4 text-gray-500 text-xs break-all max-w-[160px]">{p.device_owner || '-'}</td>
					<td class="py-2 pr-4 font-mono text-gray-400">
						{#each p.fixed_ips as ip}
							<div>{ip.ip_address}</div>
						{/each}
						{#if p.fixed_ips.length === 0}-{/if}
					</td>
					<td class="py-2 pr-4 text-gray-500">{p.project_id ? ($projectNames.get(p.project_id) ?? p.project_id.slice(0, 8)) : '-'}</td>
					<td class="py-2">
						{#if !p.device_owner || p.device_owner === ''}
							<div class="flex items-center gap-1">
								<button
									onclick={() => onEdit(p)}
									class="px-2 py-0.5 text-xs bg-gray-700 hover:bg-gray-600 text-gray-300 rounded"
								>수정</button>
								<button
									onclick={() => onDelete(p)}
									class="px-2 py-0.5 text-xs bg-red-900/30 hover:bg-red-900/50 text-red-400 rounded"
								>삭제</button>
							</div>
						{/if}
					</td>
				</tr>
			{/each}
		</tbody>
	</table>
</div>
<div class="flex items-center justify-between mt-3">
	<button
		disabled={markerStack.length === 0}
		onclick={onPrev}
		class="px-3 py-1.5 text-xs rounded bg-gray-800 hover:bg-gray-700 text-gray-300 disabled:opacity-30 disabled:cursor-not-allowed"
	>← 이전</button>
	<span class="text-xs text-gray-600">{ports.length}개 포트</span>
	<button
		disabled={!nextMarker}
		onclick={onNext}
		class="px-3 py-1.5 text-xs rounded bg-gray-800 hover:bg-gray-700 text-gray-300 disabled:opacity-30 disabled:cursor-not-allowed"
	>다음 →</button>
</div>
