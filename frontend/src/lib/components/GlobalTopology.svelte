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
		external_gateway_ips: string[];
		interface_ips: { ip_address: string; subnet_id: string }[];
		is_distributed: boolean;
		is_ha: boolean;
		connected_subnet_ids: string[];
		dvr_subnet_ids: string[];
		project_id: string | null;
	}
	interface TopologyInstance {
		id: string; name: string; status: string;
		project_id?: string | null;
		network_names: string[];
		ip_addresses: { addr: string; type: string; network_name: string; network_id?: string | null }[];
	}
	interface FloatingIpInfo {
		id: string; floating_ip_address: string;
		fixed_ip_address: string | null; status: string;
		port_id: string | null; floating_network_id: string;
		project_id?: string | null;
	}
	interface TopologyLBMember {
		id: string; address: string; protocol_port: number;
		status: string; subnet_id: string | null;
		pool_id: string; server_id: string | null;
	}
	interface TopologyLBListener {
		id: string; name: string; protocol: string;
		protocol_port: number; default_pool_id: string | null;
	}
	interface TopologyLoadBalancer {
		id: string; name: string;
		vip_address: string | null; vip_port_id: string | null;
		vip_subnet_id: string | null; vip_network_id: string | null;
		provisioning_status: string; operating_status: string;
		project_id: string | null;
		listeners: TopologyLBListener[];
		members: TopologyLBMember[];
	}
	interface TopologyData {
		networks: TopologyNetwork[];
		routers: TopologyRouter[];
		instances: TopologyInstance[];
		floating_ips: FloatingIpInfo[];
		load_balancers?: TopologyLoadBalancer[];
	}

	import { onMount } from 'svelte';

	let {
		data,
		projectId = null,
		showAll = false,
		fitWidth = false,
		onSelectInstance = undefined,
		onSelectRouter = undefined,
		onSelectLoadBalancer = undefined,
	}: {
		data: TopologyData;
		projectId?: string | null;
		showAll?: boolean;
		fitWidth?: boolean;
		onSelectInstance?: (id: string) => void;
		onSelectRouter?: (id: string) => void;
		onSelectLoadBalancer?: (lb: TopologyLoadBalancer) => void;
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
		...visibleNetworks.filter(n => n.is_external).sort((a, b) => a.name.localeCompare(b.name)),
		...visibleNetworks.filter(n => n.is_shared && !n.is_external).sort((a, b) => a.name.localeCompare(b.name)),
		...visibleNetworks.filter(n => !n.is_external && !n.is_shared).sort((a, b) => a.name.localeCompare(b.name)),
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

	// name → network id (단일 네트워크용, 이름 충돌 없는 경우 fast path)
	// admin showAll 모드에서는 아래 nameToNetworks + resolveNetId 를 사용
	const nameToNetworks = $derived.by(() => {
		const m = new Map<string, TopologyNetwork[]>();
		for (const n of data.networks) {
			const arr = m.get(n.name) ?? [];
			arr.push(n);
			m.set(n.name, arr);
		}
		return m;
	});

	// subnet_id → network_id
	const subnetNetId = $derived(new Map(
		data.networks.flatMap(n => n.subnet_details.map(s => [s.id, n.id]))
	));

	// subnet_id → SubnetDetail
	const subnetById = $derived(new Map(
		data.networks.flatMap(n => n.subnet_details.map(s => [s.id, s]))
	));

	// router id → TopologyRouter (상세 정보 툴팁용)
	const routerById = $derived(new Map(data.routers.map(r => [r.id, r])));

	// floating_ip_address → floating_network_id (외부 네트워크 ID)
	const fipNetMap = $derived(new Map(
		data.floating_ips.map(f => [f.floating_ip_address, f.floating_network_id])
	));

	// port_id → FloatingIpInfo (LB VIP의 FIP 매칭용)
	const fipPortMap = $derived(new Map(
		data.floating_ips.filter(f => f.port_id).map(f => [f.port_id!, f])
	));

	// ── Item rows ─────────────────────────────────────────────────────────────
	interface ItemRow {
		type: 'router' | 'instance';
		id: string;
		name: string;
		status: string;
		connectedNetIds: string[];   // sorted by netIdx
		netIps: Map<string, string[]>;  // netId → IP list
		floatingNetIps: Map<string, string[]>;  // ext_netId → floating IP list
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
				if (router.external_gateway_ips?.length) {
					netIps.set(router.external_gateway_network_id, [...router.external_gateway_ips]);
				}
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
				connectedNetIds, netIps, floatingNetIps: new Map(),
				leftIdx: indices.length ? Math.min(...indices) : 0,
				rightIdx: indices.length ? Math.max(...indices) : 0,
			});
		}

		// Instances
		for (const inst of data.instances.filter(i => projectId == null || i.project_id === projectId)) {
			const netSet = new Set<string>();
			const netIps = new Map<string, string[]>();
			const floatingNetIps = new Map<string, string[]>();

			for (const ipInfo of inst.ip_addresses) {
				if (ipInfo.type === 'floating') {
					const extNetId = fipNetMap.get(ipInfo.addr);
					if (extNetId) {
						const fips = floatingNetIps.get(extNetId) ?? [];
						if (!fips.includes(ipInfo.addr)) fips.push(ipInfo.addr);
						floatingNetIps.set(extNetId, fips);
					}
					continue;
				}
				const nid = ipInfo.network_id || resolveNetId(ipInfo.network_name, ipInfo.addr);
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
				connectedNetIds, netIps, floatingNetIps,
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

	// ── LB items ──────────────────────────────────────────────────────────────
	interface LBItem {
		lb: TopologyLoadBalancer;
		vipNetId: string | null;
		rowIdx: number;
	}

	const lbItems = $derived.by((): LBItem[] => {
		const lbs = (data.load_balancers ?? []).filter(lb =>
			projectId == null || lb.project_id === projectId
		);
		return lbs.map((lb, i) => {
			const vipNetId =
				lb.vip_network_id && netCX.has(lb.vip_network_id)
					? lb.vip_network_id
					: lb.vip_subnet_id
					  ? (subnetNetId.get(lb.vip_subnet_id) ?? null)
					  : null;
			return { lb, vipNetId, rowIdx: rows.length + i };
		});
	});

	// instance id → rows 인덱스 (LB 멤버 엣지 그릴 때 cy 계산용)
	const instRowIdx = $derived(new Map(
		rows.flatMap((r, i) => r.type === 'instance' ? [[r.id, i] as [string, number]] : [])
	));

	// ── SVG dimensions ────────────────────────────────────────────────────────
	const barH  = $derived(Math.max(rows.length + lbItems.length, 1) * ROW_H + 20);
	// Extra right space: items are placed to the RIGHT of their rightmost bar
	const svgW  = $derived(Math.max(640,
		L_PAD + Math.max(0, orderedNetworks.length - 1) * COL_W + IP_GAP + ITEM_W + 40
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

	// ── IP / CIDR 유틸 ────────────────────────────────────────────────────────
	function _ipToNum(ip: string): number | null {
		const parts = ip.split('.');
		if (parts.length !== 4) return null;
		const nums = parts.map(Number);
		if (nums.some(n => isNaN(n) || n < 0 || n > 255)) return null;
		return ((nums[0] << 24) | (nums[1] << 16) | (nums[2] << 8) | nums[3]) >>> 0;
	}

	function _ipv4InCidr(ip: string, cidr: string): boolean {
		const slashIdx = cidr.lastIndexOf('/');
		if (slashIdx < 0) return false;
		const net = cidr.slice(0, slashIdx);
		const mask = parseInt(cidr.slice(slashIdx + 1));
		if (isNaN(mask) || mask < 0 || mask > 32) return false;
		const ipNum = _ipToNum(ip);
		const netNum = _ipToNum(net);
		if (ipNum === null || netNum === null) return false;
		const maskBits = mask === 0 ? 0 : ((0xFFFFFFFF << (32 - mask)) >>> 0);
		return (ipNum & maskBits) === (netNum & maskBits);
	}

	/**
	 * 네트워크 이름 + IP 주소로 실제 network_id 해석.
	 * admin 모드에서 동일 이름 네트워크가 여러 프로젝트에 존재할 때
	 * 서브넷 CIDR 매칭으로 올바른 네트워크를 찾는다.
	 * floating IP 등 CIDR 미매칭 시 첫 번째 후보를 반환한다.
	 */
	function resolveNetId(networkName: string, ipAddr: string): string | undefined {
		const nets = nameToNetworks.get(networkName);
		if (!nets?.length) return undefined;
		if (nets.length === 1) return nets[0].id;
		for (const net of nets) {
			for (const subnet of net.subnet_details) {
				if (_ipv4InCidr(ipAddr, subnet.cidr)) return net.id;
			}
		}
		return nets[0].id; // fallback
	}

	/** 같은 방향(좌/우)에 N개 연결선이 있을 때 i번째 선의 Y 오프셋 계산. */
	function connectionY(cy: number, index: number, total: number, spacing = 13): number {
		if (total <= 1) return cy;
		return cy + (index - (total - 1) / 2) * spacing;
	}
</script>

{@const svgAttrs = fitWidth
	? { width: '100%', height: 'auto', preserveAspectRatio: 'xMidYMid meet' }
	: { style: `min-width:${svgW}px; height:${svgH}px;` }}
<div class={fitWidth ? 'w-full' : 'w-full overflow-auto'}>
	<svg
		viewBox="0 0 {svgW} {svgH}"
		xmlns="http://www.w3.org/2000/svg"
		{...svgAttrs}
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
			<!-- 같은 방향(좌/우)에 연결된 네트워크 목록을 미리 계산 (Y 분산용, floating 포함) -->
			{@const fipNetIds = [...row.floatingNetIps.keys()]}
			{@const allLeftNets  = [...row.connectedNetIds, ...fipNetIds].filter(id => (netCX.get(id) ?? 0) < cx)}
			{@const allRightNets = [...row.connectedNetIds, ...fipNetIds].filter(id => (netCX.get(id) ?? 0) >= cx)}
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
				{@const sideList = isLeft ? allLeftNets : allRightNets}
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

			<!-- Floating IP 점선 연결 (외부 네트워크 바 → 인스턴스 박스) -->
			{#if !isR}
				{#each [...row.floatingNetIps.entries()] as [fNetId, fIps]}
					{@const fBarX    = netCX.get(fNetId) ?? 0}
					{@const fCol     = netColors.get(fNetId) ?? '#ea580c'}
					{@const fIsLeft  = fBarX < cx}
					{@const fTargetX = fIsLeft ? ix : ix + ITEM_W}
					{@const fLabelX  = fIsLeft ? fBarX + 10 : fBarX - 10}
					{@const fAnchor  = fIsLeft ? 'start' : 'end'}
					{@const fSideAll = fIsLeft ? allLeftNets : allRightNets}
					{@const fSideIdx = fSideAll.indexOf(fNetId)}
					{@const fLineY   = connectionY(cy, fSideIdx, fSideAll.length)}
					<!-- 점선 -->
					<line
						x1={fBarX} y1={fLineY}
						x2={fTargetX} y2={fLineY}
						stroke={fCol} stroke-width="1.5" opacity="0.55"
						stroke-dasharray="6 3"
					/>
					<!-- floating IP 라벨 -->
					{#each fIps.slice(0, 2) as fip, fi2}
						<text
							x={fLabelX} y={fLineY - 5 - fi2 * 11}
							text-anchor={fAnchor}
							fill={fCol} font-size="9" opacity="0.7"
							font-family="ui-monospace, monospace"
							style="pointer-events:none"
						>{fip}</text>
					{/each}
				{/each}
			{/if}

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
				>라우터 · {row.status}{routerById.get(row.id)?.is_distributed ? ' · DVR' : ''}{routerById.get(row.id)?.is_ha ? ' · HA' : ''}</text>
				{@const rDetail = routerById.get(row.id)}
				<title>{row.name}{'\n'}ID: {row.id}{'\n'}상태: {row.status}{rDetail?.is_distributed ? '\nDVR: 활성' : ''}{rDetail?.is_ha ? '\nHA: 활성' : ''}{rDetail?.external_gateway_ips?.length ? '\nGW IP: ' + rDetail.external_gateway_ips.join(', ') : ''}{rDetail?.interface_ips?.length ? '\n인터페이스: ' + rDetail.interface_ips.map(i => i.ip_address).join(', ') : ''}</title>
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
				>인스턴스 · {trunc(row.status, 12)}</text>
				<title>{row.name}{'\n'}ID: {row.id}{'\n'}상태: {row.status}{'\n'}IP: {[...row.netIps.values()].flat().join(', ')}</title>
			{/if}
		{/each}

		<!-- ── Load Balancer nodes + edges ── -->
		{#each lbItems as { lb, vipNetId, rowIdx }}
			{@const cy   = rowCY(rowIdx)}
			{@const iy   = rowY(rowIdx)}
			{@const barX = vipNetId ? (netCX.get(vipNetId) ?? 0) : 0}
			{@const col  = vipNetId ? (netColors.get(vipNetId) ?? '#06b6d4') : '#06b6d4'}
			{@const cx   = vipNetId ? barX + IP_GAP + ITEM_W / 2 : svgW / 2}
			{@const ix   = cx - ITEM_W / 2}
			{@const isActive = lb.provisioning_status === 'ACTIVE'}
			{@const lbStroke = isActive ? '#06b6d4' : '#f59e0b'}
			{@const lbFill   = isLight ? (isActive ? '#ecfeff' : '#fffbeb') : (isActive ? '#083344' : '#1c1400')}
			{@const lbText   = isLight ? (isActive ? '#0891b2' : '#92400e') : (isActive ? '#67e8f9' : '#fcd34d')}

			<!-- VIP 네트워크 연결선 -->
			{#if vipNetId}
				<line
					x1={barX} y1={cy}
					x2={ix} y2={cy}
					stroke={col} stroke-width="2.5" opacity="0.8"
				/>
				<!-- VIP IP 라벨 -->
				{#if lb.vip_address}
					<text
						x={barX + 10} y={cy - 5}
						fill={col} font-size="9" opacity="0.85"
						font-family="ui-monospace, monospace"
						style="pointer-events:none"
					>{lb.vip_address}</text>
				{/if}
			{/if}

			<!-- FIP 점선 (LB 포트에 Floating IP가 연결된 경우) -->
			{#if lb.vip_port_id}
				{@const fip = fipPortMap.get(lb.vip_port_id)}
				{#if fip}
					{@const fBarX = netCX.get(fip.floating_network_id) ?? 0}
					{@const fCol  = netColors.get(fip.floating_network_id) ?? '#ea580c'}
					<line
						x1={fBarX} y1={cy}
						x2={ix} y2={cy}
						stroke={fCol} stroke-width="1.5" opacity="0.55"
						stroke-dasharray="6 3"
					/>
					<text
						x={fBarX + 10} y={cy - 5}
						fill={fCol} font-size="9" opacity="0.7"
						font-family="ui-monospace, monospace"
						style="pointer-events:none"
					>{fip.floating_ip_address}</text>
				{/if}
			{/if}

			<!-- 멤버 → 인스턴스 연결선 -->
			{#each lb.members as member}
				{#if member.server_id}
					{@const instIdx = instRowIdx.get(member.server_id)}
					{#if instIdx !== undefined}
						{@const instRow    = rows[instIdx]}
						{@const instCx     = itemCX(instRow)}
						{@const instCy     = rowCY(instIdx)}
						{@const mActive    = member.status === 'ACTIVE'}
						{@const mError     = member.status === 'ERROR'}
						{@const mCol       = mActive ? '#22c55e' : mError ? '#ef4444' : '#64748b'}
						<!-- 곡선 경로: LB 노드 → 인스턴스 노드 -->
						<path
							d="M{ix + ITEM_W} {cy} C{ix + ITEM_W + 40} {cy} {instCx - ITEM_W / 2 - 40} {instCy} {instCx - ITEM_W / 2} {instCy}"
							fill="none" stroke={mCol} stroke-width="1.5" opacity="0.6"
							stroke-dasharray={mActive ? 'none' : '4 2'}
						/>
					{/if}
				{/if}
			{/each}

			<!-- LB 노드 박스 -->
			<rect
				x={ix} y={iy} width={ITEM_W} height={ITEM_H} rx="10"
				fill={lbFill} stroke={lbStroke} stroke-width="1.5"
				stroke-dasharray={isActive ? 'none' : '5 3'}
				data-testid="lb-node-{lb.id}"
				style="cursor:pointer"
				role="button"
				tabindex="0"
				onclick={() => onSelectLoadBalancer?.(lb)}
				onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && onSelectLoadBalancer?.(lb)}
			/>
			<!-- LB 아이콘 (균형 막대) -->
			<line x1={ix + 22} y1={cy - 8} x2={ix + 22} y2={cy + 8}
				stroke={lbStroke} stroke-width="1.5"/>
			<line x1={ix + 14} y1={cy - 4} x2={ix + 30} y2={cy - 4}
				stroke={lbStroke} stroke-width="2"/>
			<line x1={ix + 16} y1={cy + 4} x2={ix + 28} y2={cy + 4}
				stroke={lbStroke} stroke-width="1.5" opacity="0.6"/>
			<!-- LB 이름 + 라벨 -->
			<text
				x={ix + 44} y={cy - 7}
				fill={lbText} font-size="11" font-weight="600"
				font-family="ui-sans-serif, system-ui, sans-serif"
				style="pointer-events:none"
			>{trunc(lb.name || 'LB', 11)}</text>
			<text
				x={ix + 44} y={cy + 9}
				fill={lbStroke} font-size="9"
				font-family="ui-sans-serif, system-ui, sans-serif"
				style="pointer-events:none"
			>LB · {isActive ? 'ACTIVE' : lb.provisioning_status}</text>
			<title>{lb.name}{'\n'}ID: {lb.id}{'\n'}VIP: {lb.vip_address ?? '-'}{'\n'}상태: {lb.provisioning_status}{'\n'}멤버: {lb.members.length}개</title>
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
