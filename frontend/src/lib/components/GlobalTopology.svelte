<script lang="ts">
	import { onMount, untrack, tick } from 'svelte';
	import { goto } from '$app/navigation';
	import ResourceCard from './topology/ResourceCard.svelte';
	import NetworkLane from './topology/NetworkLane.svelte';
	import ConnectionOverlay from './topology/ConnectionOverlay.svelte';
	import type {
		TopologyData, TopologyTraffic, TopologyLoadBalancer,
		ItemRow, LBItem, TopologyNetwork,
	} from './topology/types.ts';

	let {
		data,
		projectId = null,
		showAll = false,
		fitWidth: _fitWidth = false,
		traffic = null,
		onSelectInstance = undefined,
		onSelectRouter = undefined,
		onSelectLoadBalancer = undefined,
	}: {
		data: TopologyData;
		projectId?: string | null;
		showAll?: boolean;
		fitWidth?: boolean;
		traffic?: TopologyTraffic | null;
		onSelectInstance?: (id: string) => void;
		onSelectRouter?: (id: string) => void;
		onSelectLoadBalancer?: (lb: TopologyLoadBalancer) => void;
	} = $props();

	// ── State ─────────────────────────────────────────────────────────────────
	let selectedId = $state<string | null>(null);
	let hoveredId = $state<string | null>(null);
	let searchTerm = $state('');
	let highlightedNetId = $state<string | null>(null);
	let groupCollapsed = $state({ router: false, lb: false, instance: false });
	let containerEl = $state<HTMLElement | null>(null);
	let sidebarEl = $state<HTMLElement | null>(null);
	let sidebarHeight = $state(0);
	let anchors = $state(new Map<string, { x: number; y: number }>());

	// ── Color palettes ────────────────────────────────────────────────────────
	const EXT_COLORS = ['#ea580c', '#f97316'];
	const SHR_COLORS = ['#0d9488', '#14b8a6'];
	const INT_COLORS = ['#3b82f6', '#22c55e', '#a855f7', '#f59e0b', '#06b6d4', '#ec4899', '#ef4444'];

	// ── Derived: networks ─────────────────────────────────────────────────────
	const visibleNetworks = $derived(
		showAll
			? data.networks
			: data.networks.filter(n =>
				n.is_external || n.is_shared || (projectId != null && n.project_id === projectId)
			)
	);

	const orderedNetworks: TopologyNetwork[] = $derived([
		...visibleNetworks.filter(n => n.is_external).sort((a, b) => a.name.localeCompare(b.name)),
		...visibleNetworks.filter(n => n.is_shared && !n.is_external).sort((a, b) => a.name.localeCompare(b.name)),
		...visibleNetworks.filter(n => !n.is_external && !n.is_shared).sort((a, b) => a.name.localeCompare(b.name)),
	]);

	const netColors = $derived.by(() => {
		const m = new Map<string, string>();
		let eI = 0, sI = 0, iI = 0;
		for (const n of orderedNetworks) {
			if (n.is_external) m.set(n.id, EXT_COLORS[eI++ % EXT_COLORS.length]);
			else if (n.is_shared) m.set(n.id, SHR_COLORS[sI++ % SHR_COLORS.length]);
			else m.set(n.id, INT_COLORS[iI++ % INT_COLORS.length]);
		}
		return m;
	});

	const netIdx = $derived(new Map(orderedNetworks.map((n, i) => [n.id, i])));

	const nameToNetworks = $derived.by(() => {
		const m = new Map<string, TopologyNetwork[]>();
		for (const n of data.networks) { const arr = m.get(n.name) ?? []; arr.push(n); m.set(n.name, arr); }
		return m;
	});

	const subnetNetId = $derived(new Map(
		data.networks.flatMap(n => n.subnet_details.map(s => [s.id, n.id] as [string, string]))
	));

	const subnetById = $derived(new Map(
		data.networks.flatMap(n => n.subnet_details.map(s => [s.id, s]))
	));

	const fipNetMap = $derived(new Map(
		data.floating_ips.map(f => [f.floating_ip_address, f.floating_network_id])
	));

	// ── IP helpers ────────────────────────────────────────────────────────────
	function _ipToNum(ip: string): number | null {
		const parts = ip.split('.');
		if (parts.length !== 4) return null;
		const nums = parts.map(Number);
		if (nums.some(n => isNaN(n) || n < 0 || n > 255)) return null;
		return ((nums[0] << 24) | (nums[1] << 16) | (nums[2] << 8) | nums[3]) >>> 0;
	}
	function _ipv4InCidr(ip: string, cidr: string): boolean {
		const si = cidr.lastIndexOf('/');
		if (si < 0) return false;
		const mask = parseInt(cidr.slice(si + 1));
		if (isNaN(mask) || mask < 0 || mask > 32) return false;
		const ipN = _ipToNum(ip), netN = _ipToNum(cidr.slice(0, si));
		if (ipN === null || netN === null) return false;
		const mb = mask === 0 ? 0 : ((0xFFFFFFFF << (32 - mask)) >>> 0);
		return (ipN & mb) === (netN & mb);
	}
	function resolveNetId(networkName: string, ipAddr: string): string | undefined {
		const nets = nameToNetworks.get(networkName);
		if (!nets?.length) return undefined;
		if (nets.length === 1) return nets[0].id;
		for (const net of nets) for (const s of net.subnet_details) if (_ipv4InCidr(ipAddr, s.cidr)) return net.id;
		return nets[0].id;
	}

	// ── Rows ──────────────────────────────────────────────────────────────────
	const rows = $derived.by((): ItemRow[] => {
		const result: ItemRow[] = [];

		for (const router of data.routers.filter(r => projectId == null || r.project_id === projectId)) {
			const netSet = new Set<string>();
			const netIps = new Map<string, string[]>();
			if (router.external_gateway_network_id) {
				netSet.add(router.external_gateway_network_id);
				if (router.external_gateway_ips?.length) netIps.set(router.external_gateway_network_id, [...router.external_gateway_ips]);
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
			const connectedNetIds = [...netSet].sort((a, b) => (netIdx.get(a) ?? 0) - (netIdx.get(b) ?? 0));
			const indices = connectedNetIds.map(id => netIdx.get(id) ?? 0);
			result.push({
				type: 'router', id: router.id, name: router.name, status: router.status,
				connectedNetIds, netIps, floatingNetIps: new Map(),
				leftIdx: indices.length ? Math.min(...indices) : 0,
				rightIdx: indices.length ? Math.max(...indices) : 0,
			});
		}

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
			const connectedNetIds = [...netSet].sort((a, b) => (netIdx.get(a) ?? 0) - (netIdx.get(b) ?? 0));
			const indices = connectedNetIds.map(id => netIdx.get(id) ?? 0);
			result.push({
				type: 'instance', id: inst.id, name: inst.name, status: inst.status,
				connectedNetIds, netIps, floatingNetIps,
				leftIdx: indices.length ? Math.min(...indices) : 0,
				rightIdx: indices.length ? Math.max(...indices) : 0,
			});
		}

		result.sort((a, b) => {
			if (a.type !== b.type) return a.type === 'router' ? -1 : 1;
			if (a.leftIdx !== b.leftIdx) return a.leftIdx - b.leftIdx;
			return a.name.localeCompare(b.name);
		});
		return result;
	});

	const lbItems = $derived.by((): LBItem[] => {
		const lbs = (data.load_balancers ?? []).filter(lb => projectId == null || lb.project_id === projectId);
		return lbs.map(lb => {
			const vipNetId = lb.vip_network_id && netIdx.has(lb.vip_network_id)
				? lb.vip_network_id
				: lb.vip_subnet_id ? (subnetNetId.get(lb.vip_subnet_id) ?? null) : null;
			return { lb, vipNetId };
		});
	});

	// ── Traffic ───────────────────────────────────────────────────────────────
	const instNetBps = $derived.by(() => {
		const m = new Map<string, { rx_bps: number; tx_bps: number }>();
		if (!traffic?.interfaces) return m;
		for (const ifc of Object.values(traffic.interfaces)) {
			const key = `${ifc.instance_id}|${ifc.network_id}`;
			const cur = m.get(key);
			if (cur) { cur.rx_bps += ifc.rx_bps; cur.tx_bps += ifc.tx_bps; }
			else m.set(key, { rx_bps: ifc.rx_bps, tx_bps: ifc.tx_bps });
		}
		return m;
	});

	function edgeIntensity(bps: number): { opacity: number; width: number } {
		if (bps >= 1e8) return { opacity: 1.00, width: 3.5 };
		if (bps >= 1e7) return { opacity: 0.90, width: 3.0 };
		if (bps >= 1e6) return { opacity: 0.80, width: 2.5 };
		if (bps >= 1e5) return { opacity: 0.65, width: 2.0 };
		return { opacity: 0.40, width: 1.5 };
	}

	// ── Search filter ─────────────────────────────────────────────────────────
	const filteredRows = $derived.by(() => {
		if (!searchTerm.trim()) return rows;
		const q = searchTerm.toLowerCase();
		return rows.filter(r =>
			r.name.toLowerCase().includes(q) ||
			[...r.netIps.values()].flat().some(ip => ip.includes(q)) ||
			[...r.floatingNetIps.values()].flat().some(ip => ip.includes(q))
		);
	});

	const filteredLbItems = $derived.by(() => {
		if (!searchTerm.trim()) return lbItems;
		const q = searchTerm.toLowerCase();
		return lbItems.filter(({ lb }) =>
			lb.name.toLowerCase().includes(q) || (lb.vip_address ?? '').includes(q)
		);
	});

	const routerRows = $derived(filteredRows.filter(r => r.type === 'router'));
	const instanceRows = $derived(filteredRows.filter(r => r.type === 'instance'));

	// ── Connection specs for overlay ──────────────────────────────────────────
	interface ConnectionSpec {
		key: string; netId: string; color: string; opacity: number; width: number;
	}

	const connections = $derived.by((): ConnectionSpec[] => {
		const result: ConnectionSpec[] = [];
		for (const row of filteredRows) {
			const allNets = [
				...row.connectedNetIds,
				...[...row.floatingNetIps.keys()].filter(id => !row.connectedNetIds.includes(id)),
			];
			for (const netId of allNets) {
				const color = netColors.get(netId) ?? '#3b82f6';
				const bpsPair = row.type === 'instance' ? instNetBps.get(`${row.id}|${netId}`) : undefined;
				const bps = (bpsPair?.rx_bps ?? 0) + (bpsPair?.tx_bps ?? 0);
				const ei = edgeIntensity(bps);
				const isFloating = !row.connectedNetIds.includes(netId);
				result.push({
					key: `${row.id}|${netId}`,
					netId,
					color,
					opacity: isFloating ? ei.opacity * 0.6 : ei.opacity,
					width: isFloating ? 1.5 : ei.width,
				});
			}
		}
		for (const { lb, vipNetId } of filteredLbItems) {
			if (vipNetId) {
				const color = netColors.get(vipNetId) ?? '#06b6d4';
				result.push({ key: `lb|${lb.id}|${vipNetId}`, netId: vipNetId, color, opacity: 0.75, width: 2 });
			}
		}
		return result;
	});

	// ── LB → member curves ────────────────────────────────────────────────────
	interface LBCurve {
		key: string;
		x1: number; y1: number;
		x2: number; y2: number;
	}

	const lbCurves = $derived.by((): LBCurve[] => {
		const activeLbId = selectedId || hoveredId;
		if (!activeLbId) return [];
		const lbItem = filteredLbItems.find(({ lb }) => lb.id === activeLbId);
		if (!lbItem) return [];

		const result: LBCurve[] = [];
		const lbAnchorKey = lbItem.vipNetId ? `lb|${lbItem.lb.id}|${lbItem.vipNetId}` : null;
		const lbAnchor = lbAnchorKey ? anchors.get(lbAnchorKey) : null;
		if (!lbAnchor) return [];

		for (const member of lbItem.lb.members) {
			if (!member.server_id) continue;
			const row = instanceRows.find(r => r.id === member.server_id);
			if (!row) continue;
			const firstNetId = row.connectedNetIds[0];
			if (!firstNetId) continue;
			const instAnchor = anchors.get(`${row.id}|${firstNetId}`);
			if (!instAnchor) continue;
			result.push({
				key: `lb-curve|${lbItem.lb.id}|${member.id}`,
				x1: lbAnchor.x, y1: lbAnchor.y,
				x2: instAnchor.x, y2: instAnchor.y,
			});
		}
		return result;
	});

	// ── Layout constants ──────────────────────────────────────────────────────
	const LANE_W = 180;
	const LANE_GAP = 16;
	const LANE_PAD = 16;
	const SIDEBAR_W = 300;
	const STAT_CARD_H = 80;

	const canvasContentW = $derived(
		LANE_PAD * 2 + orderedNetworks.length * LANE_W + Math.max(0, orderedNetworks.length - 1) * LANE_GAP
	);

	const laneXMap = $derived.by(() => {
		const m = new Map<string, number>();
		orderedNetworks.forEach((n, i) => {
			const laneCenterInCanvas = LANE_PAD + i * (LANE_W + LANE_GAP) + LANE_W / 2;
			m.set(n.id, SIDEBAR_W + laneCenterInCanvas);
		});
		return m;
	});

	const laneHeight = $derived(Math.max(400, sidebarHeight - STAT_CARD_H));

	// ── Anchor measurement (offsetLeft/offsetTop chain, sticky-safe) ──────────
	function offsetWithin(el: HTMLElement, ancestor: HTMLElement): { x: number; y: number } {
		let x = 0, y = 0;
		let cur: HTMLElement | null = el;
		while (cur && cur !== ancestor) {
			x += cur.offsetLeft;
			y += cur.offsetTop;
			cur = cur.offsetParent as HTMLElement | null;
		}
		return { x, y };
	}

	function measureAnchors() {
		if (!sidebarEl) return;
		const m = new Map<string, { x: number; y: number }>();
		for (const el of sidebarEl.querySelectorAll<HTMLElement>('[data-anchor-key]')) {
			const key = el.dataset.anchorKey;
			if (!key) continue;
			const off = offsetWithin(el, sidebarEl);
			m.set(key, {
				x: off.x + el.offsetWidth,
				y: off.y + el.offsetHeight / 2,
			});
		}
		untrack(() => { anchors = m; });
	}

	let raf = 0;
	function scheduleMeasure() {
		cancelAnimationFrame(raf);
		raf = requestAnimationFrame(() => measureAnchors());
	}

	onMount(() => {
		const ro = new ResizeObserver((entries) => {
			for (const entry of entries) {
				if (entry.target === sidebarEl) {
					untrack(() => { sidebarHeight = entry.contentRect.height; });
				}
			}
			scheduleMeasure();
		});
		if (containerEl) ro.observe(containerEl);
		if (sidebarEl) ro.observe(sidebarEl);

		tick().then(() => {
			if (sidebarEl) sidebarHeight = sidebarEl.offsetHeight;
			measureAnchors();
		});

		return () => { ro.disconnect(); cancelAnimationFrame(raf); };
	});

	$effect(() => {
		void filteredRows; void filteredLbItems;
		scheduleMeasure();
	});

	// ── Selection ─────────────────────────────────────────────────────────────
	function selectRow(row: ItemRow) {
		selectedId = selectedId === row.id ? null : row.id;
		if (row.type === 'instance') onSelectInstance?.(row.id);
		else if (row.type === 'router') onSelectRouter?.(row.id);
	}
	function selectLb(lb: TopologyLoadBalancer) {
		selectedId = selectedId === lb.id ? null : lb.id;
		onSelectLoadBalancer?.(lb);
	}
</script>

<div class="w-full" bind:this={containerEl}>
	<!-- Header bar -->
	<div class="flex items-center gap-3 mb-4 flex-wrap">
		<input
			type="text"
			placeholder="이름 또는 IP 검색…"
			bind:value={searchTerm}
			class="text-xs px-3 py-1.5 rounded-lg bg-gray-800 border border-gray-700 text-gray-200 placeholder-gray-600
				focus:outline-none focus:border-blue-500 w-52"
		/>
		<!-- Network filter chips -->
		<div class="flex gap-1.5 flex-wrap">
			{#each orderedNetworks as net}
				{@const col = netColors.get(net.id) ?? '#3b82f6'}
				<button
					type="button"
					class="text-[10px] px-2 py-0.5 rounded-full border transition-all"
					style="border-color: {col}; color: {highlightedNetId === net.id ? '#fff' : col}; background: {highlightedNetId === net.id ? col : 'transparent'}"
					onclick={() => { highlightedNetId = highlightedNetId === net.id ? null : net.id; }}
				>{net.name || net.id}</button>
			{/each}
		</div>
		{#if traffic?.ts}
			<div class="ml-auto flex items-center gap-1.5 text-[10px] text-gray-500">
				<span class="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></span>
				Live
			</div>
		{/if}
	</div>

	<!-- Scrollable viewport: horizontal scroll stays inside this box -->
	<div class="overflow-x-auto">
		<!-- Content row: sidebar + canvas. relative for SVG overlay anchor. -->
		<div class="flex items-start relative" style="min-width: max-content">
			<!-- Left sidebar: resource cards (sticky — stays visible when scrolled right) -->
			<div
				class="sticky left-0 z-20 bg-gray-900 flex-shrink-0 flex flex-col gap-3 pr-4"
				style="width: {SIDEBAR_W}px"
				bind:this={sidebarEl}
			>
				{#if routerRows.length > 0}
					<button
						type="button"
						class="flex items-center gap-1.5 text-[10px] font-semibold text-gray-500 uppercase tracking-wide px-1 w-full text-left hover:text-gray-400 transition-colors"
						onclick={() => { groupCollapsed.router = !groupCollapsed.router; scheduleMeasure(); }}
					>
						<span class="text-gray-600">{groupCollapsed.router ? '▸' : '▾'}</span>
						라우터 ({routerRows.length})
					</button>
					{#if !groupCollapsed.router}
						{#each routerRows as row (row.id)}
							<!-- svelte-ignore a11y_no_static_element_interactions -->
							<div
								onmouseenter={() => { hoveredId = row.id; }}
								onmouseleave={() => { hoveredId = null; }}
							>
								<ResourceCard
									{row}
									{netColors}
									{instNetBps}
									selected={selectedId === row.id}
									onSelect={() => selectRow(row)}
								/>
							</div>
						{/each}
					{/if}
				{/if}

				{#if filteredLbItems.length > 0}
					<button
						type="button"
						class="flex items-center gap-1.5 text-[10px] font-semibold text-gray-500 uppercase tracking-wide px-1 mt-1 w-full text-left hover:text-gray-400 transition-colors"
						onclick={() => { groupCollapsed.lb = !groupCollapsed.lb; scheduleMeasure(); }}
					>
						<span class="text-gray-600">{groupCollapsed.lb ? '▸' : '▾'}</span>
						로드밸런서 ({filteredLbItems.length})
					</button>
					{#if !groupCollapsed.lb}
						{#each filteredLbItems as { lb, vipNetId } (lb.id)}
							<!-- svelte-ignore a11y_no_static_element_interactions -->
							<div
								onmouseenter={() => { hoveredId = lb.id; }}
								onmouseleave={() => { hoveredId = null; }}
							>
								<ResourceCard
									lbItem={{ lb, vipNetId }}
									{netColors}
									{instNetBps}
									selected={selectedId === lb.id}
									onSelect={() => selectLb(lb)}
								/>
							</div>
						{/each}
					{/if}
				{/if}

				{#if instanceRows.length > 0}
					<button
						type="button"
						class="flex items-center gap-1.5 text-[10px] font-semibold text-gray-500 uppercase tracking-wide px-1 mt-1 w-full text-left hover:text-gray-400 transition-colors"
						onclick={() => { groupCollapsed.instance = !groupCollapsed.instance; scheduleMeasure(); }}
					>
						<span class="text-gray-600">{groupCollapsed.instance ? '▸' : '▾'}</span>
						인스턴스 ({instanceRows.length})
					</button>
					{#if !groupCollapsed.instance}
						{#each instanceRows as row (row.id)}
							<!-- svelte-ignore a11y_no_static_element_interactions -->
							<div
								onmouseenter={() => { hoveredId = row.id; }}
								onmouseleave={() => { hoveredId = null; }}
							>
								<ResourceCard
									{row}
									{netColors}
									{instNetBps}
									selected={selectedId === row.id}
									onSelect={() => {
										selectRow(row);
										if (!onSelectInstance) goto(`/dashboard/instances/${row.id}`);
									}}
								/>
							</div>
						{/each}
					{/if}
				{/if}

				{#if filteredRows.length === 0 && filteredLbItems.length === 0}
					<div class="text-xs text-gray-600 px-2 py-4">리소스 없음</div>
				{/if}
			</div>

			<!-- Center canvas: network lanes -->
			<div class="flex-shrink-0" style="width: {canvasContentW}px">
				{#if orderedNetworks.length === 0}
					<div class="flex items-center justify-center h-40 text-gray-600 text-sm">
						네트워크 없음
					</div>
				{:else}
					<div class="flex" style="gap: {LANE_GAP}px; padding: 0 {LANE_PAD}px">
						{#each orderedNetworks as net (net.id)}
							<div style="width: {LANE_W}px; flex-shrink: 0">
								<NetworkLane
									{net}
									color={netColors.get(net.id) ?? '#3b82f6'}
									{traffic}
									highlighted={highlightedNetId === net.id}
									dimmed={highlightedNetId !== null && highlightedNetId !== net.id}
									{laneHeight}
								/>
							</div>
						{/each}
					</div>
				{/if}
			</div>

			<!-- SVG overlay: connection lines (absolute, covers full content width) -->
			<ConnectionOverlay
				width={SIDEBAR_W + canvasContentW}
				height={sidebarHeight || 400}
				{connections}
				{laneXMap}
				{anchors}
				{lbCurves}
				selectedKey={selectedId}
				hoveredKey={hoveredId}
			/>
		</div>
	</div>
</div>
