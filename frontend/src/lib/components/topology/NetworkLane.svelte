<script lang="ts">
	import type { TopologyNetwork, TopologyTraffic } from './types.ts';

	interface Props {
		net: TopologyNetwork;
		color: string;
		traffic?: TopologyTraffic | null;
		highlighted: boolean;
		dimmed: boolean;
		laneHeight: number;
	}

	let { net, color, traffic = null, highlighted, dimmed, laneHeight }: Props = $props();

	function formatBps(bps: number): string {
		if (bps >= 1e9) return `${(bps / 1e9).toFixed(1)}G`;
		if (bps >= 1e6) return `${(bps / 1e6).toFixed(1)}M`;
		if (bps >= 1e3) return `${(bps / 1e3).toFixed(0)}k`;
		if (bps > 0) return `${bps.toFixed(0)}b`;
		return '0b';
	}

	function trafficColor(totalBps: number): string {
		if (totalBps >= 1e8) return '#ef4444';
		if (totalBps >= 1e7) return '#f97316';
		if (totalBps >= 1e6) return '#fbbf24';
		if (totalBps >= 1e5) return '#4ade80';
		return '#64748b';
	}

	const netTraffic = $derived(traffic?.networks?.[net.id] ?? null);
	const totalBps = $derived(netTraffic ? netTraffic.rx_bps + netTraffic.tx_bps : 0);
	const cidr = $derived(net.subnet_details[0]?.cidr ?? '');
	const typeLabel = $derived(net.is_external ? '외부' : net.is_shared ? '공유' : '내부');
</script>

<div
	class="flex flex-col items-center transition-opacity duration-200"
	style="opacity: {dimmed ? 0.25 : 1}"
>
	<!-- Stat card -->
	<div
		class="rounded-lg border px-3 py-2 mb-0 text-center w-full transition-all"
		style="border-color: {color}; background: {highlighted ? color + '22' : 'rgb(17 24 39 / 0.9)'}"
	>
		<div class="text-xs font-semibold truncate" style="color: {color}">{net.name || net.id}</div>
		<div class="text-[9px] text-gray-500 mt-0.5">{typeLabel}</div>
		{#if cidr}
			<div class="text-[8px] font-mono text-gray-600 mt-0.5">{cidr}</div>
		{/if}
		{#if netTraffic && totalBps > 0}
			<div class="text-[8px] font-mono mt-1" style="color: {trafficColor(totalBps)}">
				↓{formatBps(netTraffic.rx_bps)} ↑{formatBps(netTraffic.tx_bps)}
			</div>
		{/if}
	</div>

	<!-- Vertical line -->
	<div
		class="w-0.5 transition-all duration-200"
		style="height: {laneHeight}px; background: {color}; opacity: {highlighted ? 0.9 : 0.45}"
	></div>
</div>
