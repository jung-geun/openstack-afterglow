<script lang="ts">
	import StatusChip from '$lib/components/ui/StatusChip.svelte';
	import type { InstanceItem } from '$lib/types/userDashboard';

	interface Props {
		instances: (InstanceItem & { project: string })[];
	}

	let { instances }: Props = $props();

	const PREVIEW_LIMIT = 5;
</script>

<div class="bg-gray-900 border border-gray-800 rounded-2xl p-5">
	<div class="flex items-center gap-2.5 mb-3.5">
		<div class="w-10 h-10 rounded-[10px] bg-blue-500/15 border border-blue-500/30 text-blue-400 flex items-center justify-center shrink-0">
			<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2" />
			</svg>
		</div>
		<div class="text-white font-semibold text-sm">인스턴스</div>
		<span class="ml-auto text-xs text-gray-500">{instances.length}개</span>
	</div>
	<div class="flex flex-col">
		{#each instances.slice(0, PREVIEW_LIMIT) as inst (inst.id)}
			<div class="flex items-center gap-3 py-2.5 border-b border-gray-800 last:border-b-0">
				<div class="flex-1 min-w-0">
					<div class="text-white text-[13px] font-medium truncate">{inst.name || inst.id.slice(0, 8)}</div>
					<div class="text-[11px] text-gray-500 mt-0.5 font-mono truncate">{inst.flavor_name || '—'} · {inst.project}</div>
				</div>
				<StatusChip status={inst.status} />
			</div>
		{/each}
		{#if instances.length === 0}
			<div class="text-gray-600 text-xs py-3 text-center">없음</div>
		{:else if instances.length > PREVIEW_LIMIT}
			<a href="/dashboard/instances" class="block text-center text-[11px] text-blue-400 hover:text-blue-300 transition-colors pt-2.5">
				+{instances.length - PREVIEW_LIMIT}개 더 보기 →
			</a>
		{/if}
	</div>
</div>
