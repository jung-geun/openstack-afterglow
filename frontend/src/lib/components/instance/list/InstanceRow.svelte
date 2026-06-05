<script lang="ts">
	import type { Instance } from '$lib/types/compute';
	import StatusChip from '$lib/components/ui/StatusChip.svelte';
	import InstanceIpCell from './InstanceIpCell.svelte';
	import InstanceRowActions from './InstanceRowActions.svelte';

	const strategyLabel: Record<string, string> = { prebuilt: '사전 빌드', dynamic: '동적 생성' };

	let {
		instance,
		onSelect,
		onAction,
	}: {
		instance: Instance;
		onSelect: (id: string) => void;
		onAction: (kind: 'console' | 'shelve' | 'unshelve' | 'delete', instance: Instance) => Promise<void>;
	} = $props();
</script>

<div
	class="grid grid-cols-[1fr_0px_0px_1fr_0px_0px_0px] sm:grid-cols-[1.2fr_130px_0px_1.5fr_0px_0px_32px] md:grid-cols-[1.2fr_130px_1.2fr_1.5fr_0px_0px_32px] lg:grid-cols-[1.2fr_130px_1.2fr_1.5fr_80px_80px_32px] px-4 py-3 text-[13px] items-center border-b border-gray-800 transition-colors last:border-b-0"
>
	<!-- 이름 -->
	<button
		type="button"
		onclick={() => onSelect(instance.id)}
		class="flex items-center gap-2.5 min-w-0 w-full text-left text-white hover:text-blue-400 transition-colors cursor-pointer"
	>
		<div class="shrink-0 w-7 h-7 rounded-md bg-blue-500/15 border border-blue-500/30 flex items-center justify-center">
			<svg class="w-3.5 h-3.5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2"/>
			</svg>
		</div>
		<div class="min-w-0 flex-1">
			<span class="block font-medium truncate">{instance.name}</span>
			<div class="sm:hidden mt-0.5" onclick={(e) => e.stopPropagation()} role="none"><StatusChip status={instance.status} /></div>
		</div>
	</button>
	<!-- 상태 -->
	<div class="hidden sm:block overflow-hidden px-1"><StatusChip status={instance.status} class="max-w-full truncate" /></div>
	<!-- 이미지/플레이버 -->
	<div class="hidden md:block text-xs min-w-0">
		<div class="text-gray-300 truncate">{instance.image_name ?? '볼륨에서 부팅'}</div>
		{#if instance.flavor_name}<div class="text-gray-500 mt-0.5 truncate">{instance.flavor_name}</div>{/if}
	</div>
	<!-- IP -->
	<div class="text-[11px] sm:text-xs">
		<InstanceIpCell addresses={instance.ip_addresses} />
	</div>
	<!-- 라이브러리 -->
	<div class="hidden lg:flex flex-wrap gap-1">
		{#each instance.union_libraries.filter(Boolean) as lib}
			<span class="px-1.5 py-0.5 bg-blue-900/40 text-blue-300 rounded text-xs">{lib}</span>
		{/each}
	</div>
	<!-- 전략 -->
	<div class="hidden lg:block text-gray-500 text-xs">{instance.union_strategy ? strategyLabel[instance.union_strategy] ?? instance.union_strategy : '—'}</div>
	<!-- 액션 -->
	<InstanceRowActions {instance} {onAction} />
</div>
