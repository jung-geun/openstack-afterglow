<script lang="ts">
	interface AnchorPos { x: number; y: number; }

	interface ConnectionSpec {
		key: string;         // "${rowId}|${netId}" or "lb|${lbId}|${netId}"
		netId: string;
		color: string;
		opacity: number;
		width: number;
	}

	interface Props {
		width: number;
		height: number;
		connections: ConnectionSpec[];
		laneXMap: Map<string, number>;  // netId → center X in overlay coords
		anchors: Map<string, AnchorPos>; // key → {x, y} in overlay coords
		selectedKey: string | null;      // highlighted resource id
	}

	let { width, height, connections, laneXMap, anchors, selectedKey }: Props = $props();

	interface Line {
		x1: number; y1: number; x2: number; y2: number;
		color: string; opacity: number; width: number; key: string;
	}

	const lines = $derived.by((): Line[] => {
		const result: Line[] = [];
		for (const conn of connections) {
			const anchor = anchors.get(conn.key);
			const laneX = laneXMap.get(conn.netId);
			if (!anchor || laneX === undefined) continue;

			// Dim non-selected connections when something is selected
			let opacity = conn.opacity;
			if (selectedKey) {
				const isSelected = conn.key.startsWith(selectedKey + '|') || conn.key === selectedKey;
				opacity = isSelected ? Math.min(1, conn.opacity * 1.4) : conn.opacity * 0.15;
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

<svg
	{width}
	{height}
	style="position:absolute;inset:0;pointer-events:none;overflow:visible"
	xmlns="http://www.w3.org/2000/svg"
>
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
