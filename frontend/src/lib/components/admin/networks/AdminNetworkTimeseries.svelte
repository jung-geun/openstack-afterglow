<script lang="ts">
	import type { TsPoint } from '$lib/types/resources';
	import TimeSeriesChart from '$lib/components/TimeSeriesChart.svelte';

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

<div class="mb-6">
	{#if loading}
		<div class="bg-gray-900 border border-gray-800 rounded-xl p-5 h-48 flex items-center justify-center">
			<div class="text-gray-600 text-sm">차트 로딩 중...</div>
		</div>
	{:else}
		<TimeSeriesChart
			{data}
			title="네트워크 수 추이"
			mainKey="total"
			extraKeys={['routers', 'floating_ips_used']}
			currentRange={range}
			onRangeChange={onRangeChange}
		/>
	{/if}
</div>
