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
	let account = $state<AccountMeta | null>(null);
	let loading = $state(true);
	let refreshing = $state(false);
	let deleting = $state<string | null>(null);
	let showModal = $state(false);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function load() {
		if (containers.length === 0) loading = true;
		else refreshing = true;
		await Promise.allSettled([
			api.get<SwiftContainer[]>('/api/object-storage', token, projectId)
				.then(v => { containers = v; loading = false; })
				.catch(() => { containers = []; loading = false; }),
			api.get<AccountMeta>('/api/object-storage/account', token, projectId)
				.then(v => { account = v; })
				.catch(() => {}),
		]);
		loading = false;
		refreshing = false;
	}

	async function forceRefresh() {
		refreshing = true;
		await Promise.allSettled([
			api.get<SwiftContainer[]>('/api/object-storage', token, projectId, { refresh: true })
				.then(v => { containers = v; })
				.catch(() => { containers = []; }),
			api.get<AccountMeta>('/api/object-storage/account', token, projectId, { refresh: true })
				.then(v => { account = v; })
				.catch(() => {}),
		]);
		refreshing = false;
	}

	async function createContainer(name: string): Promise<string | true> {
		try {
			await api.post('/api/object-storage', { name }, token, projectId);
			await load();
			return true;
		} catch (e) {
			return e instanceof ApiError ? e.message : '버킷 생성 실패';
		}
	}

	async function deleteContainer(name: string) {
		if (!await confirmDialog(`버킷 "${name}" 와 그 안의 모든 객체를 삭제합니다. 계속하시겠습니까?`)) return;
		deleting = name;
		try {
			await api.delete(`/api/object-storage/${encodeURIComponent(name)}`, token, projectId);
			await load();
		} catch (e) {
			toast.error('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
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
	{:else if containers.length === 0}
		<div class="text-gray-600 text-sm py-20 text-center">버킷이 없습니다</div>
	{:else}
		<BucketCardGrid {containers} {deleting} {refreshing} onDelete={deleteContainer} />
	{/if}
</div>
