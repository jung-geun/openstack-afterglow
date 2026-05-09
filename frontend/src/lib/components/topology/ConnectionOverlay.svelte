<script lang="ts">
	interface AnchorPos { x: number; y: number; }

	interface ConnectionSpec {
		key: string;         // "${rowId}|${netId}" or "lb|${lbId}|${netId}"
		netId: string;
		color: string;
		opacity: number;
		width: number;
	}

	interface LBCurve {
		key: string;
		x1: number; y1: number;
		x2: number; y2: number;
	}

	interface Props {
		width: number;
		height: number;
		connections: ConnectionSpec[];
		laneXMap: Map<string, number>;  // netId → center X in overlay coords
		anchors: Map<string, AnchorPos>; // key → {x, y} in overlay coords
		lbCurves: LBCurve[];
		selectedKey: string | null;      // selected resource id
		hoveredKey: string | null;       // hovered resource id
	}

	let { width, height, connections, laneXMap, anchors, lbCurves, selectedKey, hoveredKey }: Props = $props();

	interface Line {
		x1: number; y1: number; x2: number; y2: number;
		color: string; opacity: number; width: number; key: string;
	}

	const lines = $derived.by((): Line[] => {
		const result: Line[] = [];
		// selected takes priority over hover for highlighting
		const activeKey = selectedKey || hoveredKey;
		const dimOpacity = selectedKey ? 0.12 : 0.20;

		for (const conn of connections) {
			const anchor = anchors.get(conn.key);
			const laneX = laneXMap.get(conn.netId);
			if (!anchor || laneX === undefined) continue;

			let opacity = conn.opacity;
			if (activeKey) {
				const isActive =
					conn.key.startsWith(activeKey + '|') ||
					conn.key === activeKey ||
					conn.key.startsWith('lb|' + activeKey + '|');
				opacity = isActive ? Math.min(1, conn.opacity * 1.4) : dimOpacity;
			}

			result.push({
				x1: anchor.x, y1: anchor.y,
				x2: laneX, y2: anchor.y,
				color: conn.color,
				opacity,
				width: conn.width,
				key: conn.key,
			});
		}
		return result;
	});
</script>

<!--
	Two-layer SVG:
	- 하위 레이어(z-auto): 일반 connection lines. 사이드바(z-20) 카드 뒤에 깔려야 카드를 가리지 않음.
	- 상위 레이어(z-25): LB 곡선 + 끝점 dot. 카드 위로 올라와 시작/끝점이 가려지지 않음.
-->
<svg
	{width}
	{height}
	style="position:absolute;inset:0;pointer-events:none;overflow:visible"
	xmlns="http://www.w3.org/2000/svg"
>
	<!-- Normal connection lines: card interface row → network lane -->
	{#each lines as line (line.key)}
		<line
			x1={line.x1} y1={line.y1}
			x2={line.x2} y2={line.y2}
			stroke={line.color}
			stroke-width={line.width}
			opacity={line.opacity}
			stroke-linecap="round"
		/>
	{/each}
</svg>

<svg
	{width}
	{height}
	style="position:absolute;inset:0;pointer-events:none;overflow:visible;z-index:25"
	xmlns="http://www.w3.org/2000/svg"
>
	<!-- LB → member instance curves: dashed amber bezier -->
	{#each lbCurves as curve (curve.key)}
		<path
			d="M {curve.x1} {curve.y1} C {curve.x1 + 60} {curve.y1} {curve.x2 + 60} {curve.y2} {curve.x2} {curve.y2}"
			fill="none"
			stroke="#f59e0b"
			stroke-width="1.5"
			stroke-dasharray="4 3"
			opacity="0.75"
			stroke-linecap="round"
		/>
	{/each}

	<!-- LB curve endpoint markers: amber dots so start/end stay visible above cards -->
	{#each lbCurves as curve (curve.key + '-mk')}
		<circle cx={curve.x1} cy={curve.y1} r="3" fill="#f59e0b" />
		<circle cx={curve.x2} cy={curve.y2} r="3" fill="#f59e0b" />
	{/each}
</svg>
