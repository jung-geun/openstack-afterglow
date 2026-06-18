<script lang="ts">
	import { confirmDialog } from '$lib/stores/confirm.svelte';
	import { untrack } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import type { SwiftContainer, AccountMeta } from '$lib/types/objectStorage';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import BucketCreateDialog from '$lib/components/object-storage/BucketCreateDialog.svelte';
	import BucketCardGrid from '$lib/components/object-storage/BucketCardGrid.svelte';
	import BucketCardSkeleton from '$lib/components/object-storage/BucketCardSkeleton.svelte';
	import { toast } from '$lib/stores/toast';

	let containers = $state<SwiftContainer[]>([]);
	let deletedContainers = $state<SwiftContainer[]>([]);
	let account = $state<AccountMeta | null>(null);
	let loading = $state(true);
	let refreshing = $state(false);
	let deleting = $state<string | null>(null);
	let restoring = $state<string | null>(null);
	let showModal = $state(false);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function load() {
		if (containers.length === 0) loading = true;
		else refreshing = true;
		await Promise.allSettled([
			api.get<SwiftContainer[]>('/api/v1/object-storage', token, projectId)
				.then(v => { containers = v; loading = false; })
				.catch(() => { containers = []; loading = false; }),
			api.get<SwiftContainer[]>('/api/v1/object-storage/trash/containers', token, projectId)
				.then(v => { deletedContainers = v; })
				.catch(() => { deletedContainers = []; }),
			api.get<AccountMeta>('/api/v1/object-storage/account', token, projectId)
				.then(v => { account = v; })
				.catch(() => {}),
		]);
		loading = false;
		refreshing = false;
	}

	async function forceRefresh() {
		refreshing = true;
		await Promise.allSettled([
			api.get<SwiftContainer[]>('/api/v1/object-storage', token, projectId, { refresh: true })
				.then(v => { containers = v; })
				.catch(() => { containers = []; }),
			api.get<SwiftContainer[]>('/api/v1/object-storage/trash/containers', token, projectId)
				.then(v => { deletedContainers = v; })
				.catch(() => { deletedContainers = []; }),
			api.get<AccountMeta>('/api/v1/object-storage/account', token, projectId, { refresh: true })
				.then(v => { account = v; })
				.catch(() => {}),
		]);
		refreshing = false;
	}

	async function createContainer(name: string): Promise<string | true> {
		try {
			await api.post('/api/v1/object-storage', { name }, token, projectId);
			await load();
			return true;
		} catch (e) {
			return e instanceof ApiError ? e.message : '버킷 생성 실패';
		}
	}

	async function deleteContainer(name: string) {
		if (!await confirmDialog(`버킷 "${name}"을 휴지통으로 이동합니다. 보관 기간(기본 30일) 내에 복구할 수 있습니다. 계속하시겠습니까?`)) return;
		deleting = name;
		try {
			await api.delete(`/api/v1/object-storage/${encodeURIComponent(name)}`, token, projectId);
			await load();
		} catch (e) {
			toast.error('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			deleting = null;
		}
	}

	async function restoreContainer(name: string) {
		restoring = name;
		try {
			await api.post(`/api/v1/object-storage/trash/containers/${encodeURIComponent(name)}/restore`, {}, token, projectId);
			await load();
			toast.success(`버킷 "${name}" 복구 완료`);
		} catch (e) {
			toast.error('복구 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			restoring = null;
		}
	}

	async function purgeContainer(name: string) {
		if (!await confirmDialog(`버킷 "${name}"을 영구 삭제합니다. 이 작업은 되돌릴 수 없습니다. 계속하시겠습니까?`)) return;
		deleting = name;
		try {
			await api.delete(`/api/v1/object-storage/trash/containers/${encodeURIComponent(name)}`, token, projectId);
			await load();
		} catch (e) {
			toast.error('영구 삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			deleting = null;
		}
	}

	const ar = createAutoRefresh(() => load(), {
		storageKey: 'dashboard-object-storage',
		defaultActive: true,
		defaultInterval: 30,
		intervalOptions: [10, 15, 30, 60],
	});

	$effect(() => {
		const pid = $auth.projectId;
		if (!pid) return;
		containers = [];
		untrack(() => load());
	});
</script>

<BucketCreateDialog bind:open={showModal} onCreate={createContainer} />

<div class="p-4 md:p-8 max-w-7xl mx-auto">
	<PageHeader breadcrumb="OBJECT STORAGE / BUCKETS" title="버킷">
		{#snippet actions()}
			<AutoRefreshControl
				bind:active={ar.active}
				bind:intervalSeconds={ar.intervalSeconds}
				intervalOptions={ar.intervalOptions}
				refreshing={refreshing || loading}
				onManualRefresh={forceRefresh}
			/>
			<button
				onclick={() => (showModal = true)}
				class="text-xs text-white bg-indigo-600 hover:bg-indigo-500 transition-colors px-3 py-1.5 rounded border border-indigo-500"
			>+ 버킷 생성</button>
		{/snippet}
	</PageHeader>

	{#if loading}
		<BucketCardSkeleton />
	{:else if containers.length === 0 && deletedContainers.length === 0}
		<div class="text-gray-600 text-sm py-20 text-center">버킷이 없습니다</div>
	{:else}
		{#if containers.length > 0}
			<BucketCardGrid {containers} {deleting} {refreshing} onDelete={deleteContainer} />
		{/if}

		{#if deletedContainers.length > 0}
			<div class="mt-8">
				<h2 class="text-sm font-medium text-gray-400 mb-3 flex items-center gap-2">
					<span class="text-red-400">🗑</span> 삭제 대기 중 — 복구 가능
				</h2>
				<div class="space-y-2">
					{#each deletedContainers as c (c.name)}
						<div class="flex items-center justify-between px-4 py-3 rounded-lg border border-red-900/40 bg-red-950/10">
							<div>
								<span class="text-sm font-medium text-red-300">{c.name}</span>
								{#if c.deleted_at}
									<span class="ml-2 text-xs text-gray-500">
										{new Date(c.deleted_at * 1000).toLocaleDateString('ko-KR')} 삭제
									</span>
								{/if}
							</div>
							<div class="flex gap-2">
								<button
									onclick={() => restoreContainer(c.name)}
									disabled={restoring === c.name}
									class="text-xs text-emerald-400 hover:text-emerald-300 disabled:text-gray-600 px-2 py-1 rounded border border-emerald-900 hover:border-emerald-700 disabled:border-gray-700 transition-colors"
								>{restoring === c.name ? '복구 중...' : '복구'}</button>
								<button
									onclick={() => purgeContainer(c.name)}
									disabled={deleting === c.name}
									class="text-xs text-red-400 hover:text-red-300 disabled:text-gray-600 px-2 py-1 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors"
								>{deleting === c.name ? '삭제 중...' : '영구 삭제'}</button>
							</div>
						</div>
					{/each}
				</div>
				<p class="mt-2 text-xs text-gray-600">삭제된 버킷은 보관 기간이 지나면 자동으로 영구 삭제됩니다. 보관 기간 동안 스토리지 용량을 차지합니다.</p>
			</div>
		{/if}
	{/if}
</div>
