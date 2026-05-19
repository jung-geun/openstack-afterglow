<script lang="ts">
	import TimeSeriesChart from '$lib/components/TimeSeriesChart.svelte';
	import type { TsPoint } from '$lib/types/common';

	let {
		data,
		loading,
		range,
		onRangeChange,
	}: {
		data: TsPoint[];
		loading: boolean;
		range: string;
		onRangeChange: (r: string) => void;
	} = $props();
</script>

{#if loading}
	<div class="bg-gray-900 border border-gray-800 rounded-xl p-5 h-48 flex items-center justify-center">
		<div class="text-gray-600 text-sm">차트 로딩 중...</div>
	</div>
{:else}
	<TimeSeriesChart
		{data}
		title="파일 스토리지 수 추이"
		mainKey="total"
		currentRange={range}
		onRangeChange={onRangeChange}
	/>
{/if}
