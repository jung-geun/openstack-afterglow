<script lang="ts">
	import { confirmDialog } from '$lib/stores/confirm.svelte';
	import { untrack } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import type { Volume, VolumeBackup } from '$lib/types/resources';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import VolumeBackupCreateModal from '$lib/components/volume/backups/VolumeBackupCreateModal.svelte';
	import VolumeBackupRestoreModal from '$lib/components/volume/backups/VolumeBackupRestoreModal.svelte';
	import VolumeBackupListTable from '$lib/components/volume/backups/VolumeBackupListTable.svelte';
	import { toast } from '$lib/stores/toast';

	let backups = $state<VolumeBackup[]>([]);
	let volumes = $state<Volume[]>([]);
	let loading = $state(true);
	let refreshing = $state(false);
	let error = $state('');
	let deleting = $state<string | null>(null);

	let showModal = $state(false);
	let showRestoreModal = $state(false);
	let selectedBackup = $state<VolumeBackup | null>(null);

	async function fetchBackups() {
		try {
			backups = await api.get<VolumeBackup[]>('/api/volumes/backups', $auth.token ?? undefined, $auth.projectId ?? undefined);
			error = '';
		} catch (e) {
			error = e instanceof ApiError ? `조회 실패 (${e.status})` : '서버 오류';
		} finally {
			loading = false;
		}
	}

	async function fetchVolumes() {
		try {
			volumes = await api.get<Volume[]>('/api/volumes', $auth.token ?? undefined, $auth.projectId ?? undefined);
		} catch { /* ignore */ }
	}

	async function createBackup(form: { volume_id: string; name: string; description: string; incremental: boolean }): Promise<string | true> {
		try {
			await api.post('/api/volumes/backups', form, $auth.token ?? undefined, $auth.projectId ?? undefined);
			await fetchBackups();
			return true;
		} catch (e) {
			return e instanceof ApiError ? e.message : '생성 실패';
		}
	}

	async function restoreBackup(backupId: string): Promise<{ volume_id: string; volume_name: string } | string> {
		try {
			return await api.post<{ volume_id: string; volume_name: string }>(
				`/api/volumes/backups/${backupId}/restore`,
				{},
				$auth.token ?? undefined,
				$auth.projectId ?? undefined
			);
		} catch (e) {
			return e instanceof ApiError ? e.message : '복원 실패';
		}
	}

	async function deleteBackup(id: string, name: string) {
		if (!await confirmDialog(`백업 "${name || id.slice(0, 8)}"을 삭제하시겠습니까?`)) return;
		deleting = id;
		try {
			await api.delete(`/api/volumes/backups/${id}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
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
		storageKey: 'dashboard-volume-backups',
		defaultActive: true,
		defaultInterval: 15,
		intervalOptions: [10, 15, 30, 60],
	});

	$effect(() => {
		const pid = $auth.projectId;
		if (!pid) return;
		untrack(() => { fetchBackups(); fetchVolumes(); });
	});
</script>

<VolumeBackupCreateModal
	bind:open={showModal}
	{volumes}
	onCreate={createBackup}
/>

<VolumeBackupRestoreModal
	bind:open={showRestoreModal}
	backup={selectedBackup}
	onRestore={restoreBackup}
/>

<div class="p-4 md:p-8">
	<PageHeader breadcrumb="VOLUMES / BACKUPS" title="볼륨 백업">
		{#snippet actions()}
			<AutoRefreshControl
				bind:active={ar.active}
				bind:intervalSeconds={ar.intervalSeconds}
				intervalOptions={ar.intervalOptions}
				refreshing={refreshing}
				onManualRefresh={forceRefresh}
			/>
			<button onclick={() => showModal = true} class="bg-gray-700 hover:bg-gray-600 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">+ 백업 생성</button>
		{/snippet}
	</PageHeader>

	{#if error}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>{/if}

	{#if loading}
		<LoadingSkeleton variant="table" rows={4} />
	{:else if backups.length === 0}
		<div class="text-center py-20 text-gray-600">
			<div class="text-5xl mb-4">📦</div>
			<p class="text-lg">볼륨 백업이 없습니다</p>
		</div>
	{:else}
		<VolumeBackupListTable
			{backups}
			deletingId={deleting}
			onRestore={(b) => { selectedBackup = b; showRestoreModal = true; }}
			onDelete={deleteBackup}
		/>
	{/if}
</div>
