<script lang="ts">
	import { nodeColor } from '$lib/utils/librariesGraph';
	import type { GraphLayout } from '$lib/utils/librariesGraph';

	let {
		layout,
		onNodeClick,
	}: {
		layout: GraphLayout;
		onNodeClick: (id: string) => void;
	} = $props();

	let showGraph = $state(false);
</script>

<div class="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
	<button
		class="w-full flex items-center justify-between px-4 py-3 text-sm text-gray-300 hover:text-white hover:bg-gray-700/50 transition-colors"
		onclick={() => showGraph = !showGraph}
	>
		<span class="font-medium">의존성 그래프</span>
		<span class="text-gray-500 text-xs">{showGraph ? '▲ 접기' : '▼ 펼치기'}</span>
	</button>
	{#if showGraph}
		<div class="px-4 pb-4 overflow-x-auto">
			<svg
				width={layout.width}
				height={layout.height}
				class="min-w-full"
			>
				<defs>
					<marker id="arrowhead" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
						<polygon points="0 0, 8 3, 0 6" fill="#6b7280" />
					</marker>
				</defs>
				{#each layout.edges as edge}
					{@const fromNode = layout.nodes.find(n => n.id === edge.from)}
					{@const toNode = layout.nodes.find(n => n.id === edge.to)}
					{#if fromNode && toNode}
						<line
							x1={fromNode.posX + layout.nodeW}
							y1={fromNode.posY + layout.nodeH / 2}
							x2={toNode.posX}
							y2={toNode.posY + layout.nodeH / 2}
							stroke="#4b5563"
							stroke-width="1.5"
							marker-end="url(#arrowhead)"
						/>
					{/if}
				{/each}
				{#each layout.nodes as node}
					<g
						class="cursor-pointer"
						onclick={() => onNodeClick(node.id)}
						role="button"
						tabindex="0"
						onkeydown={(e) => e.key === 'Enter' && onNodeClick(node.id)}
					>
						<rect
							x={node.posX}
							y={node.posY}
							width={layout.nodeW}
							height={layout.nodeH}
							rx="6"
							fill="#1f2937"
							stroke={nodeColor(node.status)}
							stroke-width="1.5"
						/>
						<circle
							cx={node.posX + 12}
							cy={node.posY + layout.nodeH / 2}
							r="4"
							fill={nodeColor(node.status)}
						/>
						<text
							x={node.posX + 22}
							y={node.posY + layout.nodeH / 2 + 4}
							fill="#e5e7eb"
							font-size="11"
							font-family="system-ui, sans-serif"
						>{node.name}</text>
					</g>
				{/each}
			</svg>
			<div class="flex items-center gap-4 mt-3 text-xs text-gray-500">
				{#each [['ready','#16a34a','빌드 완료'], ['building','#2563eb','빌드 중'], ['failed','#dc2626','빌드 실패'], ['none','#4b5563','미빌드']] as [, color, label]}
					<span class="flex items-center gap-1">
						<span class="inline-block w-2 h-2 rounded-full" style="background:{color}"></span>{label}
					</span>
				{/each}
			</div>
		</div>
	{/if}
</div>
