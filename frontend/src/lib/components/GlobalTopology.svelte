<script lang="ts">
	import { goto } from '$app/navigation';

	interface SubnetDetail {
		id: string; name: string; cidr: string;
		gateway_ip: string | null; dhcp_enabled: boolean;
	}
	interface TopologyNetwork {
		id: string; name: string; status: string;
		is_external: boolean; is_shared: boolean;
		project_id: string | null;
		subnet_details: SubnetDetail[];
	}
	interface TopologyRouter {
		id: string; name: string; status: string;
		external_gateway_network_id: string | null;
		connected_subnet_ids: string[];
		project_id: string | null;
	}
	interface TopologyInstance {
		id: string; name: string; status: string;
		network_names: string[];
		ip_addresses: { addr: string; type: string; network_name: string }[];
	}
	interface FloatingIpInfo {
		id: string; floating_ip_address: string;
		fixed_ip_address: string | null; status: string;
		port_id: string | null; floating_network_id: string;
		project_id?: string | null;
	}
	interface TopologyData {
		networks: TopologyNetwork[];
		routers: TopologyRouter[];
		instances: TopologyInstance[];
		floating_ips: FloatingIpInfo[];
	}

	import { onMount } from 'svelte';

	let {
		data,
		projectId = null,
		showAll = false,
		onSelectInstance = undefined,
		onSelectRouter = undefined,
	}: {
		data: TopologyData;
		projectId?: string | null;
		showAll?: boolean;
		onSelectInstance?: (id: string) => void;
		onSelectRouter?: (id: string) => void;
	} = $props();

	// ── Light mode detection ──────────────────────────────────────────────────
	let isLight = $state(false);
	onMount(() => {
		isLight = document.documentElement.classList.contains('light');
		const obs = new MutationObserver(() => {
			isLight = document.documentElement.classList.contains('light');
		});
		obs.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
		return () => obs.disconnect();
	});

	// ── Layout constants ──────────────────────────────────────────────────────
	const COL_W     = 380;   // horizontal spacing between network bar centers
	const L_PAD     = 80;    // left padding (충분히 넓혀야 왼쪽 badge가 짤리지 않음)
	const TOP_H     = 56;    // height above the bars for top badges
	const ROW_H     = 100;   // vertical spacing per item row
	const ITEM_W    = 164;   // item box width
	const ITEM_H    = 56;    // item box height
	const BAR_W     = 8;     // network bar width
	const BOT_H     = 70;    // height below bars for bottom labels (name + CIDRs)
	const ICON_R    = 11;    // router circle radius
	const IP_GAP    = 100;   // min gap between bar and item box (space for IP labels)

	// ── Color palettes ────────────────────────────────────────────────────────
	const EXT_COLORS = ['#ea580c', '#f97316'];
	const SHR_COLORS = ['#0d9488', '#14b8a6'];
	const INT_COLORS = ['#3b82f6', '#22c55e', '#a855f7', '#f59e0b', '#06b6d4', '#ec4899', '#ef4444'];

	// ── Derived: network ordering ─────────────────────────────────────────────
	// Show: external networks + shared networks + networks owned by current project
	const visibleNetworks = $derived(
		showAll
			? data.networks
			: data.networks.filter(n =>
				n.is_external ||
				n.is_shared ||
				(projectId != null && n.project_id === projectId)
			)
	);

	const orderedNetworks = $derived([
		...visibleNetworks.filter(n => n.is_external),
		...visibleNetworks.filter(n => n.is_shared && !n.is_external),
		...visibleNetworks.filter(n => !n.is_external && !n.is_shared),
	]);

	const netColors = $derived.by(() => {
		const m = new Map<string, string>();
		let eI = 0, sI = 0, iI = 0;
		for (const n of orderedNetworks) {
			if (n.is_external)      m.set(n.id, EXT_COLORS[eI++ % EXT_COLORS.length]);
			else if (n.is_shared)   m.set(n.id, SHR_COLORS[sI++ % SHR_COLORS.length]);
			else                    m.set(n.id, INT_COLORS[iI++ % INT_COLORS.length]);
		}
		return m;
	});

	// Bar center X per network
	const netCX = $derived(new Map(
		orderedNetworks.map((n, i) => [n.id, L_PAD + i * COL_W])
	));

	// Index per network (for sorting)
	const netIdx = $derived(new Map(orderedNetworks.map((n, i) => [n.id, i])));

	// name → network id
	const nameToNetId = $derived(new Map(data.networks.map(n => [n.name, n.id])));

	// subnet_id → network_id
	const subnetNetId = $derived(new Map(
		data.networks.flatMap(n => n.subnet_details.map(s => [s.id, n.id]))
	));

	// subnet_id → SubnetDetail
	const subnetById = $derived(new Map(
		data.networks.flatMap(n => n.subnet_details.map(s => [s.id, s]))
	));

	// ── Item rows ─────────────────────────────────────────────────────────────
	interface ItemRow {
		type: 'router' | 'instance';
		id: string;
		name: string;
		status: string;
		connectedNetIds: string[];   // sorted by netIdx
		netIps: Map<string, string[]>;  // netId → IP list
		leftIdx: number;
		rightIdx: number;
	}

	const rows = $derived.by((): ItemRow[] => {
		const result: ItemRow[] = [];

		// Routers — only include routers belonging to the current project
		const projectRouters = data.routers.filter(r =>
			projectId == null || r.project_id === projectId
		);
		for (const router of projectRouters) {
			const netSet = new Set<string>();
			const netIps = new Map<string, string[]>();

			if (router.external_gateway_network_id) {
				netSet.add(router.external_gateway_network_id);
			}
			for (const sid of router.connected_subnet_ids) {
				const nid = subnetNetId.get(sid);
				if (!nid) continue;
				netSet.add(nid);
				const subnet = subnetById.get(sid);
				if (subnet?.gateway_ip) {
					const ips = netIps.get(nid) ?? [];
					if (!ips.includes(subnet.gateway_ip)) ips.push(subnet.gateway_ip);
					netIps.set(nid, ips);
				}
			}

			const connectedNetIds = [...netSet].sort(
				(a, b) => (netIdx.get(a) ?? 0) - (netIdx.get(b) ?? 0)
			);
			const indices = connectedNetIds.map(id => netIdx.get(id) ?? 0);
			result.push({
				type: 'router', id: router.id, name: router.name, status: router.status,
				connectedNetIds, netIps,
				leftIdx: indices.length ? Math.min(...indices) : 0,
				rightIdx: indices.length ? Math.max(...indices) : 0,
			});
		}

		// Instances
		for (const inst of data.instances) {
			const netSet = new Set<string>();
			const netIps = new Map<string, string[]>();

			for (const ipInfo of inst.ip_addresses) {
				const nid = nameToNetId.get(ipInfo.network_name);
				if (!nid) continue;
				netSet.add(nid);
				const ips = netIps.get(nid) ?? [];
				if (!ips.includes(ipInfo.addr)) ips.push(ipInfo.addr);
				netIps.set(nid, ips);
			}

			const connectedNetIds = [...netSet].sort(
				(a, b) => (netIdx.get(a) ?? 0) - (netIdx.get(b) ?? 0)
			);
			const indices = connectedNetIds.map(id => netIdx.get(id) ?? 0);
			result.push({
				type: 'instance', id: inst.id, name: inst.name, status: inst.status,
				connectedNetIds, netIps,
				leftIdx: indices.length ? Math.min(...indices) : 0,
				rightIdx: indices.length ? Math.max(...indices) : 0,
			});
		}

		// Sort: routers first, then by leftmost network index
		result.sort((a, b) => {
			if (a.type !== b.type) return a.type === 'router' ? -1 : 1;
			if (a.leftIdx !== b.leftIdx) return a.leftIdx - b.leftIdx;
			return a.name.localeCompare(b.name);
		});

		return result;
	});

	// ── SVG dimensions ────────────────────────────────────────────────────────
	const barH  = $derived(Math.max(rows.length, 1) * ROW_H + 20);
	// Extra right space: items are placed to the RIGHT of their rightmost bar
	const svgW  = $derived(Math.max(640,
		L_PAD + orderedNetworks.length * COL_W + IP_GAP + ITEM_W + 40
	));
	const svgH  = $derived(TOP_H + barH + BOT_H);

	// ── Helpers ───────────────────────────────────────────────────────────────
	function rowY(i: number)  { return TOP_H + i * ROW_H; }
	function rowCY(i: number) { return rowY(i) + ITEM_H / 2; }

	function itemCX(row: ItemRow): number {
		if (!row.connectedNetIds.length) return svgW / 2;
		const xs = row.connectedNetIds
			.map(id => netCX.get(id))
			.filter((x): x is number => x !== undefined);
		if (!xs.length) return svgW / 2;
		// 2개 이상 네트워크에 연결된 경우: 가장 왼쪽 바 오른쪽에 배치 (단일 네트워크와 동일)
		if (xs.length > 1) {
			const leftX = Math.min(...xs);
			return leftX + IP_GAP + ITEM_W / 2;
		}
		// 단일 네트워크: bar 오른쪽에 배치
		return xs[0] + IP_GAP + ITEM_W / 2;
	}

	function instStroke(status: string) {
		if (status === 'ACTIVE') return '#22c55e';
		if (status === 'ERROR' || status === 'SHUTOFF') return '#ef4444';
		return '#78716c';
	}
	function instFill(status: string) {
		if (isLight) {
			if (status === 'ACTIVE') return '#f0fdf4';
			if (status === 'ERROR' || status === 'SHUTOFF') return '#fef2f2';
			return '#f8fafc';
		}
		if (status === 'ACTIVE') return '#052e16';
		if (status === 'ERROR' || status === 'SHUTOFF') return '#450a0a';
		return '#1c1917';
	}
	function instText(status: string) {
		if (isLight) {
			if (status === 'ACTIVE') return '#15803d';
			if (status === 'ERROR' || status === 'SHUTOFF') return '#dc2626';
			return '#64748b';
		}
		if (status === 'ACTIVE') return '#4ade80';
		if (status === 'ERROR' || status === 'SHUTOFF') return '#f87171';
		return '#a8a29e';
	}

	function routerHasExtGw(row: ItemRow): boolean {
		return row.connectedNetIds.some(id => {
			const n = orderedNetworks.find(x => x.id === id);
			return n?.is_external ?? false;
		});
	}

	function trunc(s: string, n: number): string {
		return s.length > n ? s.slice(0, n - 1) + '…' : s;
	}

	/** 같은 방향(좌/우)에 N개 연결선이 있을 때 i번째 선의 Y 오프셋 계산. */
	function connectionY(cy: number, index: number, total: number, spacing = 13): number {
		if (total <= 1) return cy;
		return cy + (index - (total - 1) / 2) * spacing;
	}
</script>

<div class="w-full overflow-auto">
	<svg
		viewBox="0 0 {svgW} {svgH}"
		style="min-width:{svgW}px; height:{svgH}px;"
		xmlns="http://www.w3.org/2000/svg"
	>
		<!-- ── Network vertical bars ── -->
		{#each orderedNetworks as net}
			{@const cx   = netCX.get(net.id) ?? 0}
			{@const col  = netColors.get(net.id) ?? '#3b82f6'}
			{@const bx   = cx - BAR_W / 2}

			<!-- Bar -->
			<rect
				x={bx} y={TOP_H - 4}
				width={BAR_W} height={barH + 4}
				rx="4" fill={col}
			/>

			<!-- Top badge -->
			<rect
				x={cx - 72} y={8}
				width={144} height={34}
				rx="6"
				fill={isLight ? '#f8fafc' : '#111827'} stroke={col} stroke-width="1.5"
				style="cursor:pointer"
				role="button"
				tabindex="0"
				onclick={() => goto(`/dashboard/networks/${net.id}`)}
				onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && goto(`/dashboard/networks/${net.id}`)}
			/>
			<text
				x={cx} y={20}
				text-anchor="middle" fill={col}
				font-size="10" font-weight="600"
				font-family="ui-sans-serif, system-ui, sans-serif"
				style="pointer-events:none"
			>{trunc(net.name || net.id, 18)}</text>
			<text
				x={cx} y={34}
				text-anchor="middle" fill={col}
				font-size="9" opacity="0.75"
				font-family="ui-sans-serif, system-ui, sans-serif"
				style="pointer-events:none"
			>{net.is_external ? '외부 네트워크' : net.is_shared ? '공유 네트워크' : `내부 · ${net.subnet_details.length}서브넷`}</text>

			<!-- Bottom label: network name -->
			<text
				x={cx} y={svgH - 50}
				text-anchor="middle" fill={col}
				font-size="10" opacity="0.6"
				font-family="ui-sans-serif, system-ui, sans-serif"
			>{trunc(net.name || net.id, 18)}</text>
			<!-- Bottom label: subnet CIDRs -->
			{#each net.subnet_details as subnet, si}
				<text
					x={cx} y={svgH - 36 + si * 13}
					text-anchor="middle" fill={col}
					font-size="9" opacity="0.5"
					font-family="ui-monospace, monospace"
					style="pointer-events:none"
				>{subnet.cidr}</text>
			{/each}
		{/each}

		<!-- ── Item rows ── -->
		{#each rows as row, i}
			{@const cy   = rowCY(i)}
			{@const iy   = rowY(i)}
			{@const cx   = itemCX(row)}
			{@const ix   = cx - ITEM_W / 2}
			{@const isR  = row.type === 'router'}
			{@const rHasGw = isR && routerHasExtGw(row)}
			{@const rStroke = rHasGw ? '#f59e0b' : '#64748b'}
			{@const rFill   = isLight ? (rHasGw ? '#fffbeb' : '#f8fafc') : (rHasGw ? '#1c1400' : '#0f172a')}
			{@const rText   = isLight ? (rHasGw ? '#92400e' : '#475569') : (rHasGw ? '#fcd34d' : '#94a3b8')}
			{@const iStroke = instStroke(row.status)}
			{@const iFill   = instFill(row.status)}
			{@const iText   = instText(row.status)}

			<!-- Connection lines + IP labels -->
			<!-- 같은 방향(좌/우)에 연결된 네트워크 목록을 미리 계산 (Y 분산용) -->
			{@const leftNets  = row.connectedNetIds.filter(id => (netCX.get(id) ?? 0) < cx)}
			{@const rightNets = row.connectedNetIds.filter(id => (netCX.get(id) ?? 0) >= cx)}

			{#if isR && row.connectedNetIds.length > 1}
				{@const leftBarX  = netCX.get(row.connectedNetIds[0]) ?? 0}
				{@const rightBarX = netCX.get(row.connectedNetIds[row.connectedNetIds.length - 1]) ?? 0}
				<!-- 라우터 브리징 선: 연결된 모든 네트워크 바를 가로지름 -->
				<line
					x1={leftBarX} y1={cy}
					x2={rightBarX} y2={cy}
					stroke="#64748b" stroke-width="3" opacity="0.4"
					stroke-dasharray="6 3"
				/>
			{/if}

			{#each row.connectedNetIds as netId}
				{@const barX = netCX.get(netId) ?? 0}
				{@const col  = netColors.get(netId) ?? '#3b82f6'}
				{@const ips  = row.netIps.get(netId) ?? []}
				{@const isLeft   = barX < cx}
				{@const sideList = isLeft ? leftNets : rightNets}
				{@const sideIdx  = sideList.indexOf(netId)}
				{@const lineY    = connectionY(cy, sideIdx, sideList.length)}
				<!-- 최대 2개 IP만 라벨로 표시 -->
				{@const visibleIps = ips.slice(0, 2)}
				{@const hiddenCount = ips.length - visibleIps.length}
				{@const targetX  = isLeft ? ix : ix + ITEM_W}
				{@const ipLabelX = isLeft ? barX + 10 : barX - 10}
				{@const ipAnchor = isLeft ? 'start' : 'end'}

				<!-- Horizontal line: bar → item box edge (Y 분산 적용) -->
				<line
					x1={barX} y1={lineY}
					x2={targetX} y2={lineY}
					stroke={col} stroke-width="2.5" opacity="0.8"
				/>

				<!-- DVR 라우터: 같은 네트워크에 이중 포트가 있으면 두 번째 선 표시 -->
				{#if isR}
					{@const dvrNets = new Set(
						(row as typeof row & { dvr_subnet_ids?: string[] }).dvr_subnet_ids
							?.map((sid: string) => {
								const nid = [...(data.networks || [])].find(n =>
									n.subnet_details.some(s => s.id === sid)
								)?.id;
								return nid;
							})
							.filter(Boolean) ?? []
					)}
					{#if dvrNets.has(netId)}
						<line
							x1={barX} y1={lineY + 5}
							x2={targetX} y2={lineY + 5}
							stroke={col} stroke-width="1.5" opacity="0.45"
							stroke-dasharray="4 2"
						/>
					{/if}
				{/if}

				<!-- IP labels: 선 위쪽, 바 방향 기준 -->
				{#each visibleIps as ip, ipIdx}
					<text
						x={ipLabelX}
						y={lineY - 5 - ipIdx * 11}
						text-anchor={ipAnchor}
						fill={col} font-size="9" opacity="0.85"
						font-family="ui-monospace, monospace"
						style="pointer-events:none"
					>{ip}</text>
				{/each}
				{#if hiddenCount > 0}
					<text
						x={ipLabelX}
						y={lineY - 5 - visibleIps.length * 11}
						text-anchor={ipAnchor}
						fill={col} font-size="8" opacity="0.6"
						font-family="ui-sans-serif, sans-serif"
						style="pointer-events:none"
					>+{hiddenCount}개</text>
				{/if}
			{/each}

			<!-- Item box -->
			{#if isR}
				<!-- Router -->
				<rect
					x={ix} y={iy} width={ITEM_W} height={ITEM_H} rx="28"
					fill={rFill} stroke={rStroke} stroke-width="1.5"
					style={onSelectRouter ? 'cursor:pointer' : ''}
					role="button"
					tabindex="0"
					onclick={() => onSelectRouter?.(row.id)}
					onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && onSelectRouter?.(row.id)}
				/>
				<!-- Router icon (circle with ↻-like marks) -->
				<circle cx={ix + 26} cy={cy} r={ICON_R}
					fill="none" stroke={rStroke} stroke-width="1.5"/>
				<circle cx={ix + 26} cy={cy} r="4"
					fill={rStroke} opacity="0.6"/>
				<!-- Name + label -->
				<text
					x={ix + 44} y={cy - 7}
					fill={rText} font-size="11" font-weight="600"
					font-family="ui-sans-serif, system-ui, sans-serif"
					style="pointer-events:none"
				>{trunc(row.name, 11)}</text>
				<text
					x={ix + 44} y={cy + 9}
					fill={rStroke} font-size="9"
					font-family="ui-sans-serif, system-ui, sans-serif"
					style="pointer-events:none"
				>라우터 · {row.status}</text>
				<title>{row.name}{'\n'}ID: {row.id}{'\n'}상태: {row.status}</title>
			{:else}
				<!-- Instance -->
				<rect
					x={ix} y={iy} width={ITEM_W} height={ITEM_H} rx="8"
					fill={iFill} stroke={iStroke} stroke-width="1.5"
					style="cursor:pointer"
					role="button"
					tabindex="0"
					onclick={() => onSelectInstance ? onSelectInstance(row.id) : goto(`/dashboard/instances/${row.id}`)}
					onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && (onSelectInstance ? onSelectInstance(row.id) : goto(`/dashboard/instances/${row.id}`))}
				/>
				<!-- Instance icon (simple disk/cylinder outline) -->
				<ellipse cx={ix + 22} cy={cy - 6} rx="9" ry="4"
					fill="none" stroke={iStroke} stroke-width="1.3"/>
				<line x1={ix + 13} y1={cy - 6} x2={ix + 13} y2={cy + 6}
					stroke={iStroke} stroke-width="1.3"/>
				<line x1={ix + 31} y1={cy - 6} x2={ix + 31} y2={cy + 6}
					stroke={iStroke} stroke-width="1.3"/>
				<path d="M{ix + 13} {cy + 6} a9 4 0 0 0 18 0"
					fill="none" stroke={iStroke} stroke-width="1.3"/>
				<!-- Name + label -->
				<text
					x={ix + 44} y={cy - 7}
					fill={iText} font-size="11" font-weight="600"
					font-family="ui-sans-serif, system-ui, sans-serif"
					style="pointer-events:none"
				>{trunc(row.name, 11)}</text>
				<text
					x={ix + 44} y={cy + 9}
					fill={iStroke} font-size="9"
					font-family="ui-sans-serif, system-ui, sans-serif"
					style="pointer-events:none"
				>인스턴스 · {row.status}</text>
				<title>{row.name}{'\n'}ID: {row.id}{'\n'}상태: {row.status}{'\n'}IP: {[...row.netIps.values()].flat().join(', ')}</title>
			{/if}
		{/each}

		<!-- Empty state -->
		{#if data.networks.length === 0}
			<text
				x={svgW / 2} y={svgH / 2}
				text-anchor="middle" fill="#475569" font-size="14"
				font-family="ui-sans-serif, system-ui, sans-serif"
			>네트워크 없음</text>
		{/if}
	</svg>
</div>
