<script lang="ts">
	import type { Instance } from '$lib/types/resources';
	import InstanceRow from './InstanceRow.svelte';

	let {
		instances,
		onSelect,
		onAction,
	}: {
		instances: Instance[];
		onSelect: (id: string) => void;
		onAction: (kind: 'console' | 'shelve' | 'unshelve' | 'delete', instance: Instance) => Promise<void>;
	} = $props();
</script>

<div class="overflow-x-auto">
	<div class="bg-[#0B1220] border border-gray-800 rounded-[10px] overflow-hidden">
		<div class="grid grid-cols-[1fr_0px_0px_1fr_0px_0px_0px] sm:grid-cols-[1.2fr_130px_0px_1.5fr_0px_0px_32px] md:grid-cols-[1.2fr_130px_1.2fr_1.5fr_0px_0px_32px] lg:grid-cols-[1.2fr_130px_1.2fr_1.5fr_80px_80px_32px] px-4 py-2.5 border-b border-gray-800 text-[11px] uppercase tracking-wider text-gray-500 font-medium">
			<div>이름</div>
			<div class="hidden sm:block">상태</div>
			<div class="hidden md:block">이미지 / 플레이버</div>
			<div>IP</div>
			<div class="hidden lg:block">라이브러리</div>
			<div class="hidden lg:block">전략</div>
			<div></div>
		</div>
		{#each instances as inst (inst.id)}
			<InstanceRow instance={inst} {onSelect} {onAction} />
		{/each}
	</div>
</div>
