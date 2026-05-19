<script lang="ts">
	import { confirmDialog } from '$lib/stores/confirm.svelte';
	import { untrack } from 'svelte';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import type { Instance, Volume } from '$lib/types/resources';
	import VolumePageHeader from '$lib/components/volume/VolumePageHeader.svelte';
	import VolumeBasicInfoCard from '$lib/components/volume/VolumeBasicInfoCard.svelte';
	import VolumeAttachmentsTable from '$lib/components/volume/VolumeAttachmentsTable.svelte';
	import { toast } from '$lib/stores/toast';

	let volume = $state<Volume | null>(null);
	let attachedInstances = $state<Map<string, string>>(new Map());
	let loading = $state(true);
	let error = $state('');
	let deleting = $state(false);

	const ar = createAutoRefresh(() => {
		const id = $page.params.id;
		if (id) fetchVolume(id);
	}, {
		storageKey: 'dashboard-volume-detail',
		defaultActive: true,
		defaultInterval: 15,
		intervalOptions: [10, 15, 30, 60],
	});

	$effect(() => {
		const id = $page.params.id;
		if (!id || !$auth.token) return;
		untrack(() => fetchVolume(id));
	});

	async function fetchVolume(id: string) {
		loading = true;
		error = '';
		try {
			volume = await api.get<Volume>(
				`/api/volumes/${id}`,
				$auth.token ?? undefined,
				$auth.projectId ?? undefined
			);
			if (volume.attachments.length > 0) {
				const map = new Map<string, string>();
				await Promise.allSettled(
					volume.attachments.map(async (a) => {
						const serverId = (a as Record<string, string>).server_id;
						if (!serverId) return;
						try {
							const inst = await api.get<Instance>(
								`/api/instances/${serverId}`,
								$auth.token ?? undefined,
								$auth.projectId ?? undefined
							);
							map.set(serverId, inst.name);
						} catch {
							map.set(serverId, serverId.slice(0, 8) + '…');
						}
					})
				);
				attachedInstances = map;
			}
		} catch (e) {
			error = e instanceof ApiError ? `조회 실패 (${e.status}): ${e.message}` : '서버 오류';
		} finally {
			loading = false;
		}
	}

	async function deleteVolume() {
		if (!volume) return;
		if (volume.attachments.length > 0) {
			toast.warning('연결된 볼륨은 삭제할 수 없습니다. 먼저 인스턴스에서 분리하세요.');
			return;
		}
		if (!await confirmDialog(`볼륨 "${volume.name || volume.id}"을 삭제하시겠습니까?`)) return;
		deleting = true;
		try {
			await api.delete(`/api/volumes/${volume.id}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
			goto('/dashboard');
		} catch (e) {
			toast.error('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			deleting = false;
		}
	}
</script>

<div class="p-4 md:p-8 max-w-4xl mx-auto">
	<div class="mb-6">
		<a href="/dashboard" class="text-gray-400 hover:text-gray-200 text-sm transition-colors">
			← 대시보드
		</a>
	</div>

	{#if error}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">
			{error}
		</div>
	{:else if loading}
		<LoadingSkeleton variant="card" rows={5} />
	{:else if volume}
		<VolumePageHeader {volume} {deleting} onDelete={deleteVolume}>
			{#snippet actions()}
				<AutoRefreshControl
					bind:active={ar.active}
					bind:intervalSeconds={ar.intervalSeconds}
					intervalOptions={ar.intervalOptions}
					refreshing={loading}
					onManualRefresh={() => { const id = $page.params.id; if (id) fetchVolume(id); }}
				/>
			{/snippet}
		</VolumePageHeader>
		<VolumeBasicInfoCard {volume} />
		<VolumeAttachmentsTable attachments={volume.attachments} {attachedInstances} />
	{/if}
</div>
