<script lang="ts">
	import { untrack } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import type { DbBackup, DbInstance, DbFlavor } from '$lib/types/database';
	import { confirmDialog } from '$lib/stores/confirm.svelte';
	import { toast } from '$lib/stores/toast';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import StatusChip from '$lib/components/ui/StatusChip.svelte';
	import DbRestoreModal from '$lib/components/database/DbRestoreModal.svelte';

	let backups = $state<DbBackup[]>([]);
	let instances = $state<DbInstance[]>([]);
	let flavors = $state<DbFlavor[]>([]);
	let loading = $state(true);
	let refreshing = $state(false);
	let error = $state('');
	let deleting = $state<string | null>(null);

	let showRestoreModal = $state(false);
	let selectedBackup = $state<DbBackup | null>(null);

	const STUCK_MS = 6 * 3600 * 1000;
	function isStuck(b: DbBackup): boolean {
		return b.status === 'BUILDING' && (Date.now() - new Date(b.created_at).getTime()) > STUCK_MS;
	}

	// client-side join: backup.instance_id → instance
	function findInstance(b: DbBackup): DbInstance | undefined {
		if (!b.instance_id) return undefined;
		return instances.find(i => i.id === b.instance_id);
	}

	function formatSize(size: number | undefined): string {
		if (!size) return '-';
		return `${size} GB`;
	}

	function formatDate(dt: string | undefined): string {
		if (!dt) return '-';
		return dt.slice(0, 10);
	}

	function datastoreLabel(b: DbBackup): string {
		const ds = b.datastore;
		if (!ds) return '-';
		const parts = [ds.type, ds.version].filter(Boolean);
		return parts.length > 0 ? parts.join(' ') : '-';
	}

	async function fetchBackups() {
		try {
			backups = await api.get<DbBackup[]>('/api/v1/database-instances/backups', $auth.token ?? undefined, $auth.projectId ?? undefined);
			error = '';
		} catch (e) {
			error = e instanceof ApiError ? `조회 실패 (${e.status})` : '서버 오류';
		} finally {
			loading = false;
		}
	}

	async function fetchInstances() {
		try {
			instances = await api.get<DbInstance[]>('/api/v1/database-instances', $auth.token ?? undefined, $auth.projectId ?? undefined);
		} catch { /* ignore */ }
	}

	async function fetchFlavors() {
		try {
			flavors = await api.get<DbFlavor[]>('/api/v1/database-instances/flavors', $auth.token ?? undefined, $auth.projectId ?? undefined);
		} catch { /* ignore */ }
	}

	async function restoreBackup(backupId: string, name: string, flavorId: string, volumeSize: number) {
		await api.post('/api/v1/database-instances/restore', {
			backup_id: backupId, name, flavor_id: flavorId, volume_size: volumeSize,
		}, $auth.token ?? undefined, $auth.projectId ?? undefined);
		toast.success('복원 인스턴스 생성이 시작되었습니다.');
		await fetchBackups();
	}

	async function deleteBackup(id: string, name: string, stuck: boolean) {
		const baseMsg = `백업 "${name || id.slice(0, 8)}"을 삭제하시겠습니까?`;
		const stuckNote = stuck
			? '\n\nTrove 백업 레코드만 제거됩니다. Swift에 저장된 데이터는 이미 없을 수 있습니다.'
			: '';
		if (!await confirmDialog(baseMsg + stuckNote)) return;
		deleting = id;
		try {
			await api.delete(`/api/v1/database-instances/backups/${id}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
			await fetchBackups();
		} catch (e) {
			toast.error('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			deleting = null;
		}
	}

	async function forceRefresh() {
		refreshing = true;
		try {
			await fetchBackups();
		} finally {
			refreshing = false;
		}
	}

	const ar = createAutoRefresh(() => fetchBackups(), {
		storageKey: 'dashboard-db-backups',
		defaultActive: true,
		defaultInterval: 15,
		intervalOptions: [10, 15, 30, 60],
	});

	$effect(() => {
		const pid = $auth.projectId;
		if (!pid) return;
		untrack(() => {
			fetchBackups();
			fetchInstances();
			fetchFlavors();
		});
	});
</script>

<DbRestoreModal
	bind:open={showRestoreModal}
	backup={selectedBackup}
	{flavors}
	onRestore={restoreBackup}
	onClose={() => { showRestoreModal = false; }}
/>

<div class="p-4 md:p-8">
	<PageHeader breadcrumb="DATABASE / BACKUPS" title="DB 백업">
		{#snippet actions()}
			<AutoRefreshControl
				bind:active={ar.active}
				bind:intervalSeconds={ar.intervalSeconds}
				intervalOptions={ar.intervalOptions}
				refreshing={refreshing}
				onManualRefresh={forceRefresh}
			/>
		{/snippet}
	</PageHeader>

	{#if error}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>
	{/if}

	{#if loading}
		<LoadingSkeleton variant="table" rows={4} />
	{:else if backups.length === 0}
		<div class="text-center py-20 text-gray-600">
			<div class="text-5xl mb-4">🗄️</div>
			<p class="text-lg">DB 백업이 없습니다</p>
		</div>
	{:else}
		<div class="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b border-gray-800 text-gray-500 text-xs">
						<th class="text-left px-4 py-3 font-medium">이름</th>
						<th class="text-left px-4 py-3 font-medium">상태</th>
						<th class="text-left px-4 py-3 font-medium">원본 DB</th>
						<th class="text-left px-4 py-3 font-medium">Datastore</th>
						<th class="text-left px-4 py-3 font-medium">크기</th>
						<th class="text-left px-4 py-3 font-medium">생성일</th>
						<th class="text-right px-4 py-3 font-medium">액션</th>
					</tr>
				</thead>
				<tbody>
					{#each backups as b}
						{@const inst = findInstance(b)}
						{@const stuck = isStuck(b)}
						<tr class="border-t border-gray-800/50 hover:bg-gray-800/30 transition-colors">
							<td class="px-4 py-3 text-white font-medium">{b.name || b.id.slice(0, 8)}</td>
							<td class="px-4 py-3">
								<div class="flex items-center gap-1">
									<StatusChip status={b.status} />
									{#if stuck}
										<span
											class="text-xs text-red-400 ml-1"
											title="Trove guest agent가 백업 업로드를 완료하지 못했습니다. 삭제 후 재시도하세요."
										>멈춤</span>
									{/if}
								</div>
							</td>
							<td class="px-4 py-3">
								{#if inst}
									<a
										href="/dashboard/database/instances/{inst.id}"
										class="text-blue-400 hover:text-blue-300 transition-colors"
									>{inst.name}</a>
								{:else if b.instance_id}
									<span class="text-gray-600 text-xs">원본 삭제됨</span>
									{#if b.datastore?.type}
										<span class="text-gray-600 text-xs ml-1">({b.datastore.type})</span>
									{/if}
								{:else}
									<span class="text-gray-600">—</span>
								{/if}
							</td>
							<td class="px-4 py-3 text-gray-400 text-xs">{datastoreLabel(b)}</td>
							<td class="px-4 py-3 text-gray-400 text-xs">{formatSize(b.size)}</td>
							<td class="px-4 py-3 text-gray-500 text-xs">{formatDate(b.created_at)}</td>
							<td class="px-4 py-3">
								<div class="flex justify-end gap-1">
									<button
										onclick={() => { selectedBackup = b; showRestoreModal = true; }}
										class="text-blue-400 hover:text-blue-300 text-xs px-2 py-0.5 rounded border border-blue-900 hover:border-blue-700 transition-colors"
									>복원</button>
									<button
										onclick={() => deleteBackup(b.id, b.name, stuck)}
										disabled={deleting === b.id}
										class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-0.5 rounded border border-red-900 hover:border-red-700 transition-colors"
									>{deleting === b.id ? '...' : '삭제'}</button>
								</div>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>
