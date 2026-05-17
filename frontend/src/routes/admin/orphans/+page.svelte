<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import OrphanSection from '$lib/components/admin/orphans/OrphanSection.svelte';
	import OrphanCleanupModal from '$lib/components/admin/orphans/OrphanCleanupModal.svelte';
	import { pruneSelection, removeFromSelection } from '$lib/utils/selectionSet';

	interface OrphanFipInfo {
		id: string;
		address: string;
		project_id: string | null;
		created_at: string | null;
		age_days: number;
	}
	interface OrphanVolumeInfo {
		id: string;
		name: string | null;
		size_gb: number;
		project_id: string | null;
		status: string;
		created_at: string | null;
		age_days: number;
	}
	interface OrphanShareInfo {
		id: string;
		name: string | null;
		size_gb: number;
		project_id: string | null;
		status: string;
		created_at: string | null;
		age_days: number;
		snapshot_count: number;
	}
	interface OrphanSecurityGroupInfo {
		id: string;
		name: string;
		description: string | null;
		project_id: string | null;
		created_at: string | null;
		age_days: number;
	}
	interface OrphanScanResponse {
		floating_ips: OrphanFipInfo[];
		volumes: OrphanVolumeInfo[];
		manila_shares: OrphanShareInfo[];
		security_groups: OrphanSecurityGroupInfo[];
	}
	interface CleanupResult {
		deleted: string[];
		failed: { id: string; error: string }[];
	}
	type Kind = 'floating_ip' | 'volume' | 'manila_share' | 'security_group';

	let fips = $state<OrphanFipInfo[]>([]);
	let volumes = $state<OrphanVolumeInfo[]>([]);
	let shares = $state<OrphanShareInfo[]>([]);
	let secgroups = $state<OrphanSecurityGroupInfo[]>([]);
	let loading = $state(true);
	let scanError = $state('');
	let minAgeDays = $state(14);

	let selectedFips = $state(new Set<string>());
	let selectedVolumes = $state(new Set<string>());
	let selectedShares = $state(new Set<string>());
	let selectedSGs = $state(new Set<string>());

	let confirmKind = $state<Kind | null>(null);
	let confirmIds = $state<string[]>([]);
	let cleaning = $state(false);
	let cleanupError = $state('');
	let cleanupResult = $state<CleanupResult | null>(null);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	const SELECTION_GETTERS: Record<Kind, () => Set<string>> = {
		floating_ip: () => selectedFips,
		volume: () => selectedVolumes,
		manila_share: () => selectedShares,
		security_group: () => selectedSGs,
	};
	const SELECTION_SETTERS: Record<Kind, (v: Set<string>) => void> = {
		floating_ip: (v) => (selectedFips = v),
		volume: (v) => (selectedVolumes = v),
		manila_share: (v) => (selectedShares = v),
		security_group: (v) => (selectedSGs = v),
	};

	async function load() {
		loading = true;
		scanError = '';
		try {
			const data = await api.get<OrphanScanResponse>(
				`/api/admin/orphans?min_age_days=${minAgeDays}`,
				token,
				projectId
			);
			fips = data.floating_ips;
			volumes = data.volumes;
			shares = data.manila_shares ?? [];
			secgroups = data.security_groups ?? [];
			selectedFips = pruneSelection(selectedFips, fips);
			selectedVolumes = pruneSelection(selectedVolumes, volumes);
			selectedShares = pruneSelection(selectedShares, shares);
			selectedSGs = pruneSelection(selectedSGs, secgroups);
		} catch (e) {
			scanError = e instanceof ApiError ? e.message : '스캔 실패';
			fips = [];
			volumes = [];
			shares = [];
			secgroups = [];
		} finally {
			loading = false;
		}
	}

	function openConfirm(kind: Kind) {
		const ids = [...SELECTION_GETTERS[kind]()];
		if (ids.length === 0) return;
		confirmKind = kind;
		confirmIds = ids;
		cleanupError = '';
		cleanupResult = null;
	}

	async function runCleanup() {
		if (!confirmKind || confirmIds.length === 0) return;
		cleaning = true;
		cleanupError = '';
		try {
			const res = await api.post<CleanupResult>(
				'/api/admin/orphans/cleanup',
				{ kind: confirmKind, ids: confirmIds },
				token,
				projectId
			);
			cleanupResult = res;
			SELECTION_SETTERS[confirmKind](
				removeFromSelection(SELECTION_GETTERS[confirmKind](), res.deleted)
			);
			await load();
		} catch (e) {
			cleanupError = e instanceof ApiError ? e.message : '정리 실패';
		} finally {
			cleaning = false;
		}
	}

	function closeConfirm() {
		confirmKind = null;
		confirmIds = [];
		cleanupError = '';
		cleanupResult = null;
	}

	const ar = createAutoRefresh(load, {
		storageKey: 'admin-orphans',
		defaultActive: false,
		defaultInterval: 60,
		intervalOptions: [30, 60, 120]
	});

	onMount(load);
</script>

<div class="p-4 md:p-8 max-w-7xl mx-auto">
	<PageHeader breadcrumb="시스템 / 고아 리소스" title="고아 리소스 정리">
		{#snippet actions()}
			<AutoRefreshControl
				bind:active={ar.active}
				bind:intervalSeconds={ar.intervalSeconds}
				intervalOptions={ar.intervalOptions}
				refreshing={loading}
				onManualRefresh={load}
			/>
		{/snippet}
	</PageHeader>

	<div class="bg-gray-900 border border-gray-800 rounded-xl p-4 mb-6 flex flex-wrap items-center gap-4 text-sm">
		<div class="flex items-center gap-2">
			<label for="min-age" class="text-gray-400 text-xs uppercase tracking-wide">Volume 최소 연령(일)</label>
			<input
				id="min-age"
				type="number"
				min="1"
				max="365"
				bind:value={minAgeDays}
				onchange={load}
				class="w-20 bg-gray-800 border border-gray-600 rounded-lg px-2 py-1 text-white text-sm focus:outline-none"
			/>
		</div>
		<div class="text-xs text-gray-500">
			Floating IP는 분리된 즉시 후보. Volume은 status=available + attachments=[] + 연령 ≥ 임계치.
		</div>
	</div>

	{#if scanError}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">
			{scanError}
		</div>
	{/if}

	{#if loading}
		<div class="text-gray-500 text-sm">로딩 중...</div>
	{:else}
		<OrphanSection
			title="분리된 Floating IPs"
			items={fips}
			bind:selected={selectedFips}
			emptyMessage="분리된 Floating IP 없음."
			onCleanup={() => openConfirm('floating_ip')}
		>
			{#snippet headers()}
				<th class="text-left py-2 pr-4">주소</th>
				<th class="text-left py-2 pr-4">프로젝트</th>
				<th class="text-left py-2 pr-4">생성일</th>
				<th class="text-left py-2 pr-4">연령(일)</th>
				<th class="text-left py-2 pr-4">ID</th>
			{/snippet}
			{#snippet row(f)}
				<td class="py-2 pr-4 font-mono text-green-400">{f.address}</td>
				<td class="py-2 pr-4 text-gray-500 font-mono">{f.project_id?.slice(0, 8) ?? '-'}</td>
				<td class="py-2 pr-4 text-gray-400">{f.created_at?.slice(0, 10) ?? '-'}</td>
				<td class="py-2 pr-4 text-amber-400">{f.age_days}</td>
				<td class="py-2 pr-4 text-gray-500 font-mono">{f.id.slice(0, 8)}</td>
			{/snippet}
		</OrphanSection>

		<OrphanSection
			title="장기 미사용 Volumes"
			items={volumes}
			bind:selected={selectedVolumes}
			emptyMessage="임계치({minAgeDays}일) 이상의 장기 미사용 volume 없음."
			onCleanup={() => openConfirm('volume')}
		>
			{#snippet headers()}
				<th class="text-left py-2 pr-4">이름</th>
				<th class="text-left py-2 pr-4">크기(GB)</th>
				<th class="text-left py-2 pr-4">상태</th>
				<th class="text-left py-2 pr-4">프로젝트</th>
				<th class="text-left py-2 pr-4">생성일</th>
				<th class="text-left py-2 pr-4">연령(일)</th>
				<th class="text-left py-2 pr-4">ID</th>
			{/snippet}
			{#snippet row(v)}
				<td class="py-2 pr-4 text-gray-200">{v.name ?? '-'}</td>
				<td class="py-2 pr-4 text-gray-300 font-mono">{v.size_gb}</td>
				<td class="py-2 pr-4 text-green-400">{v.status}</td>
				<td class="py-2 pr-4 text-gray-500 font-mono">{v.project_id?.slice(0, 8) ?? '-'}</td>
				<td class="py-2 pr-4 text-gray-400">{v.created_at?.slice(0, 10) ?? '-'}</td>
				<td class="py-2 pr-4 text-amber-400">{v.age_days}</td>
				<td class="py-2 pr-4 text-gray-500 font-mono">{v.id.slice(0, 8)}</td>
			{/snippet}
		</OrphanSection>

		<OrphanSection
			title="고아 Manila Share"
			items={shares}
			bind:selected={selectedShares}
			emptyMessage="Keystone 프로젝트가 사라진 share 없음."
			onCleanup={() => openConfirm('manila_share')}
		>
			{#snippet headers()}
				<th class="text-left py-2 pr-4">이름</th>
				<th class="text-left py-2 pr-4">크기(GB)</th>
				<th class="text-left py-2 pr-4">상태</th>
				<th class="text-left py-2 pr-4">사라진 프로젝트</th>
				<th class="text-left py-2 pr-4">생성일</th>
				<th class="text-left py-2 pr-4">연령(일)</th>
				<th class="text-left py-2 pr-4">ID</th>
			{/snippet}
			{#snippet row(s)}
				<td class="py-2 pr-4 text-gray-200">{s.name ?? '-'}</td>
				<td class="py-2 pr-4 text-gray-300 font-mono">{s.size_gb}</td>
				<td class="py-2 pr-4 text-green-400">{s.status}</td>
				<td class="py-2 pr-4 text-gray-500 font-mono">{s.project_id?.slice(0, 8) ?? '-'}</td>
				<td class="py-2 pr-4 text-gray-400">{s.created_at?.slice(0, 10) ?? '-'}</td>
				<td class="py-2 pr-4 text-amber-400">{s.age_days}</td>
				<td class="py-2 pr-4 text-gray-500 font-mono">{s.id.slice(0, 8)}</td>
			{/snippet}
		</OrphanSection>

		<OrphanSection
			title="고아 Security Group"
			items={secgroups}
			bind:selected={selectedSGs}
			emptyMessage="afterglow-managed marker가 있는 미부착 SG 없음."
			onCleanup={() => openConfirm('security_group')}
		>
			{#snippet headerNote()}
				<div class="text-xs text-gray-500 mb-2">
					※ description에 <code class="text-gray-400">[afterglow-managed]</code> 마커가 있고 어떤 port에도 attach되지 않은 SG만 후보.
				</div>
			{/snippet}
			{#snippet headers()}
				<th class="text-left py-2 pr-4">이름</th>
				<th class="text-left py-2 pr-4">설명</th>
				<th class="text-left py-2 pr-4">프로젝트</th>
				<th class="text-left py-2 pr-4">생성일</th>
				<th class="text-left py-2 pr-4">연령(일)</th>
				<th class="text-left py-2 pr-4">ID</th>
			{/snippet}
			{#snippet row(g)}
				<td class="py-2 pr-4 text-gray-200">{g.name}</td>
				<td class="py-2 pr-4 text-gray-400 max-w-md truncate" title={g.description ?? ''}>{g.description ?? '-'}</td>
				<td class="py-2 pr-4 text-gray-500 font-mono">{g.project_id?.slice(0, 8) ?? '-'}</td>
				<td class="py-2 pr-4 text-gray-400">{g.created_at?.slice(0, 10) ?? '-'}</td>
				<td class="py-2 pr-4 text-amber-400">{g.age_days}</td>
				<td class="py-2 pr-4 text-gray-500 font-mono">{g.id.slice(0, 8)}</td>
			{/snippet}
		</OrphanSection>
	{/if}
</div>

<OrphanCleanupModal
	kind={confirmKind}
	ids={confirmIds}
	{cleaning}
	{cleanupError}
	{cleanupResult}
	onConfirm={runCleanup}
	onClose={closeConfirm}
/>
