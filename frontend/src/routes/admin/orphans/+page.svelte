<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';

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
	interface OrphanScanResponse {
		floating_ips: OrphanFipInfo[];
		volumes: OrphanVolumeInfo[];
	}
	interface CleanupResult {
		deleted: string[];
		failed: { id: string; error: string }[];
	}
	type Kind = 'floating_ip' | 'volume';

	let fips = $state<OrphanFipInfo[]>([]);
	let volumes = $state<OrphanVolumeInfo[]>([]);
	let loading = $state(true);
	let scanError = $state('');

	let minAgeDays = $state(14);

	let selectedFips = $state(new Set<string>());
	let selectedVolumes = $state(new Set<string>());

	let confirmKind = $state<Kind | null>(null);
	let confirmIds = $state<string[]>([]);
	let cleaning = $state(false);
	let cleanupError = $state('');
	let cleanupResult = $state<CleanupResult | null>(null);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

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
			// 응답에서 사라진 ID는 선택에서도 제거
			selectedFips = new Set([...selectedFips].filter((id) => fips.some((f) => f.id === id)));
			selectedVolumes = new Set(
				[...selectedVolumes].filter((id) => volumes.some((v) => v.id === id))
			);
		} catch (e) {
			scanError = e instanceof ApiError ? e.message : '스캔 실패';
			fips = [];
			volumes = [];
		} finally {
			loading = false;
		}
	}

	function toggleFip(id: string) {
		const next = new Set(selectedFips);
		if (next.has(id)) next.delete(id);
		else next.add(id);
		selectedFips = next;
	}
	function toggleAllFips() {
		if (selectedFips.size === fips.length) selectedFips = new Set();
		else selectedFips = new Set(fips.map((f) => f.id));
	}
	function toggleVolume(id: string) {
		const next = new Set(selectedVolumes);
		if (next.has(id)) next.delete(id);
		else next.add(id);
		selectedVolumes = next;
	}
	function toggleAllVolumes() {
		if (selectedVolumes.size === volumes.length) selectedVolumes = new Set();
		else selectedVolumes = new Set(volumes.map((v) => v.id));
	}

	function openConfirm(kind: Kind) {
		const ids = kind === 'floating_ip' ? [...selectedFips] : [...selectedVolumes];
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
			// 성공 항목은 선택에서 제거
			if (confirmKind === 'floating_ip') {
				const next = new Set(selectedFips);
				for (const id of res.deleted) next.delete(id);
				selectedFips = next;
			} else {
				const next = new Set(selectedVolumes);
				for (const id of res.deleted) next.delete(id);
				selectedVolumes = next;
			}
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

<div class="p-4 md:p-8 max-w-6xl">
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
		<!-- Floating IPs 섹션 -->
		<section class="mb-8">
			<div class="flex items-center justify-between mb-3">
				<h2 class="text-base font-semibold text-white">분리된 Floating IPs ({fips.length})</h2>
				<button
					onclick={() => openConfirm('floating_ip')}
					disabled={selectedFips.size === 0}
					class="px-3 py-1.5 bg-red-600 hover:bg-red-500 text-white text-xs font-medium rounded-lg disabled:opacity-30"
				>
					선택 {selectedFips.size}개 정리
				</button>
			</div>

			{#if fips.length === 0}
				<div class="text-xs text-gray-500 bg-gray-900 border border-gray-800 rounded-lg p-4">
					분리된 Floating IP 없음.
				</div>
			{:else}
				<div class="overflow-x-auto">
					<table class="w-full text-sm">
						<thead>
							<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
								<th class="text-left py-2 pr-4 w-8">
									<input
										type="checkbox"
										checked={selectedFips.size === fips.length && fips.length > 0}
										onchange={toggleAllFips}
									/>
								</th>
								<th class="text-left py-2 pr-4">주소</th>
								<th class="text-left py-2 pr-4">프로젝트</th>
								<th class="text-left py-2 pr-4">생성일</th>
								<th class="text-left py-2 pr-4">연령(일)</th>
								<th class="text-left py-2 pr-4">ID</th>
							</tr>
						</thead>
						<tbody>
							{#each fips as f (f.id)}
								<tr
									class="border-b border-gray-800/50 text-xs hover:bg-gray-800/30 transition-colors"
									class:bg-red-900-10={selectedFips.has(f.id)}
								>
									<td class="py-2 pr-4">
										<input
											type="checkbox"
											checked={selectedFips.has(f.id)}
											onchange={() => toggleFip(f.id)}
										/>
									</td>
									<td class="py-2 pr-4 font-mono text-green-400">{f.address}</td>
									<td class="py-2 pr-4 text-gray-500 font-mono">{f.project_id?.slice(0, 8) ?? '-'}</td>
									<td class="py-2 pr-4 text-gray-400">{f.created_at?.slice(0, 10) ?? '-'}</td>
									<td class="py-2 pr-4 text-amber-400">{f.age_days}</td>
									<td class="py-2 pr-4 text-gray-500 font-mono">{f.id.slice(0, 8)}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</section>

		<!-- Volumes 섹션 -->
		<section class="mb-4">
			<div class="flex items-center justify-between mb-3">
				<h2 class="text-base font-semibold text-white">장기 미사용 Volumes ({volumes.length})</h2>
				<button
					onclick={() => openConfirm('volume')}
					disabled={selectedVolumes.size === 0}
					class="px-3 py-1.5 bg-red-600 hover:bg-red-500 text-white text-xs font-medium rounded-lg disabled:opacity-30"
				>
					선택 {selectedVolumes.size}개 정리
				</button>
			</div>

			{#if volumes.length === 0}
				<div class="text-xs text-gray-500 bg-gray-900 border border-gray-800 rounded-lg p-4">
					임계치({minAgeDays}일) 이상의 장기 미사용 volume 없음.
				</div>
			{:else}
				<div class="overflow-x-auto">
					<table class="w-full text-sm">
						<thead>
							<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
								<th class="text-left py-2 pr-4 w-8">
									<input
										type="checkbox"
										checked={selectedVolumes.size === volumes.length && volumes.length > 0}
										onchange={toggleAllVolumes}
									/>
								</th>
								<th class="text-left py-2 pr-4">이름</th>
								<th class="text-left py-2 pr-4">크기(GB)</th>
								<th class="text-left py-2 pr-4">상태</th>
								<th class="text-left py-2 pr-4">프로젝트</th>
								<th class="text-left py-2 pr-4">생성일</th>
								<th class="text-left py-2 pr-4">연령(일)</th>
								<th class="text-left py-2 pr-4">ID</th>
							</tr>
						</thead>
						<tbody>
							{#each volumes as v (v.id)}
								<tr class="border-b border-gray-800/50 text-xs hover:bg-gray-800/30 transition-colors">
									<td class="py-2 pr-4">
										<input
											type="checkbox"
											checked={selectedVolumes.has(v.id)}
											onchange={() => toggleVolume(v.id)}
										/>
									</td>
									<td class="py-2 pr-4 text-gray-200">{v.name ?? '-'}</td>
									<td class="py-2 pr-4 text-gray-300 font-mono">{v.size_gb}</td>
									<td class="py-2 pr-4 text-green-400">{v.status}</td>
									<td class="py-2 pr-4 text-gray-500 font-mono">{v.project_id?.slice(0, 8) ?? '-'}</td>
									<td class="py-2 pr-4 text-gray-400">{v.created_at?.slice(0, 10) ?? '-'}</td>
									<td class="py-2 pr-4 text-amber-400">{v.age_days}</td>
									<td class="py-2 pr-4 text-gray-500 font-mono">{v.id.slice(0, 8)}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</section>
	{/if}
</div>

<!-- 정리 확인 모달 -->
{#if confirmKind}
	<div
		class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
		onclick={closeConfirm}
		role="dialog"
		onkeydown={(e) => e.key === 'Escape' && closeConfirm()}
		tabindex="-1"
	>
		<div
			class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-lg mx-4 shadow-2xl"
			onclick={(e) => e.stopPropagation()}
			role="document"
		>
			<h2 class="text-lg font-semibold text-white mb-3">
				{confirmKind === 'floating_ip' ? 'Floating IP' : 'Volume'} 정리 ({confirmIds.length}개)
			</h2>
			{#if !cleanupResult}
				<p class="text-sm text-gray-400 mb-4">
					아래 ID 목록을 OpenStack에서 삭제합니다. 이 작업은 되돌릴 수 없습니다.
				</p>
				<div class="bg-gray-950 border border-gray-800 rounded-lg p-3 mb-4 max-h-48 overflow-y-auto">
					<ul class="text-xs font-mono text-gray-300 space-y-0.5">
						{#each confirmIds as id}
							<li>{id}</li>
						{/each}
					</ul>
				</div>
				{#if confirmKind === 'volume'}
					<p class="text-xs text-amber-400 mb-3">
						※ 삭제 직전 재조회로 attachments / status를 한 번 더 검증합니다(race 방지).
					</p>
				{/if}
				{#if cleanupError}
					<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">
						{cleanupError}
					</div>
				{/if}
				<div class="flex justify-end gap-3">
					<button
						onclick={closeConfirm}
						class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium rounded-lg"
					>
						취소
					</button>
					<button
						onclick={runCleanup}
						disabled={cleaning}
						class="px-4 py-2 bg-red-600 hover:bg-red-500 text-white text-sm font-medium rounded-lg disabled:opacity-30"
					>
						{cleaning ? '정리 중...' : '정리'}
					</button>
				</div>
			{:else}
				<div class="space-y-3 mb-4">
					<div class="text-sm text-green-400">
						성공: {cleanupResult.deleted.length}개
					</div>
					{#if cleanupResult.deleted.length > 0}
						<details class="bg-gray-950 border border-gray-800 rounded-lg p-3">
							<summary class="text-xs text-gray-400 cursor-pointer">삭제된 ID 보기</summary>
							<ul class="text-xs font-mono text-gray-400 mt-2 space-y-0.5 max-h-32 overflow-y-auto">
								{#each cleanupResult.deleted as id}
									<li>{id}</li>
								{/each}
							</ul>
						</details>
					{/if}
					<div class="text-sm {cleanupResult.failed.length > 0 ? 'text-red-400' : 'text-gray-500'}">
						실패: {cleanupResult.failed.length}개
					</div>
					{#if cleanupResult.failed.length > 0}
						<div class="bg-red-900/20 border border-red-800 rounded-lg p-3 max-h-48 overflow-y-auto">
							<ul class="text-xs space-y-1.5">
								{#each cleanupResult.failed as f}
									<li>
										<span class="font-mono text-red-300">{f.id.slice(0, 8)}</span>
										<span class="text-red-400 ml-2">{f.error}</span>
									</li>
								{/each}
							</ul>
						</div>
					{/if}
				</div>
				<div class="flex justify-end">
					<button
						onclick={closeConfirm}
						class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg"
					>
						닫기
					</button>
				</div>
			{/if}
		</div>
	</div>
{/if}
