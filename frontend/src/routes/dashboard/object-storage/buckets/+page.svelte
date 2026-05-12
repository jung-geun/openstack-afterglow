<script lang="ts">
	import { untrack } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import { formatStorage } from '$lib/utils/format';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import { validateBucketName } from '$lib/utils/bucketName';

	interface SwiftContainer {
		name: string;
		count: number;
		bytes: number;
	}

	interface AccountMeta {
		container_count: number;
		object_count: number;
		bytes_used: number;
	}

	let containers = $state<SwiftContainer[]>([]);
	let account = $state<AccountMeta | null>(null);
	let loading = $state(true);
	let refreshing = $state(false);
	let deleting = $state<string | null>(null);

	// 생성 모달
	let showModal = $state(false);
	let creating = $state(false);
	let createError = $state('');
	let newName = $state('');

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

	async function createContainer() {
		const trimmed = newName.trim();
		if (!trimmed) return;
		const validationError = validateBucketName(trimmed);
		if (validationError) {
			createError = validationError;
			return;
		}
		creating = true;
		createError = '';
		try {
			await api.post('/api/object-storage', { name: trimmed }, token, projectId);
			showModal = false;
			newName = '';
			await load();
		} catch (e) {
			createError = e instanceof ApiError ? e.message : '버킷 생성 실패';
		} finally {
			creating = false;
		}
	}

	async function deleteContainer(name: string) {
		if (!confirm(`버킷 "${name}" 와 그 안의 모든 객체를 삭제합니다. 계속하시겠습니까?`)) return;
		deleting = name;
		try {
			await api.delete(`/api/object-storage/${encodeURIComponent(name)}`, token, projectId);
			await load();
		} catch (e) {
			alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
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

{#if showModal}
	<div
		class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
		onclick={() => { showModal = false; createError = ''; }}
		role="dialog"
		aria-modal="true"
		tabindex="-1"
		onkeydown={(e) => e.key === 'Escape' && (showModal = false)}
	>
		<div
			class="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md mx-4 shadow-2xl"
			onclick={(e) => e.stopPropagation()}
			role="none"
			onkeydown={(e) => e.stopPropagation()}
		>
			<h2 class="text-lg font-semibold text-white mb-4">버킷 생성</h2>
			<div class="space-y-3">
				<div>
					<label class="block text-xs text-gray-400 mb-1">이름</label>
					<input
						type="text"
						bind:value={newName}
						placeholder="my-container"
						class="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
						onkeydown={(e) => e.key === 'Enter' && createContainer()}
					/>
				</div>
				{#if createError}
					<p class="text-red-400 text-xs">{createError}</p>
				{/if}
			</div>
			<div class="flex justify-end gap-2 mt-5">
				<button
					onclick={() => { showModal = false; createError = ''; newName = ''; }}
					class="px-4 py-2 text-sm text-gray-400 hover:text-white border border-gray-700 rounded-lg transition-colors"
				>취소</button>
				<button
					onclick={createContainer}
					disabled={creating || !newName.trim()}
					class="px-4 py-2 text-sm bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded-lg transition-colors"
				>{creating ? '생성 중...' : '생성'}</button>
			</div>
		</div>
	</div>
{/if}

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
				onclick={() => { showModal = true; createError = ''; newName = ''; }}
				class="text-xs text-white bg-indigo-600 hover:bg-indigo-500 transition-colors px-3 py-1.5 rounded border border-indigo-500"
			>+ 버킷 생성</button>
		{/snippet}
	</PageHeader>

	{#if loading}
		<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
			{#each Array(6) as _}
				<div class="animate-pulse h-32 bg-gray-900 border border-gray-800 rounded-2xl"></div>
			{/each}
		</div>
	{:else if containers.length === 0}
		<div class="text-gray-600 text-sm py-20 text-center">버킷이 없습니다</div>
	{:else}
		<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5" class:opacity-60={refreshing} class:pointer-events-none={refreshing}>
			{#each containers as c}
				<div class="bg-gray-900 border border-gray-800 rounded-2xl p-5">
					<!-- Header -->
					<div class="flex items-center gap-2.5 mb-3">
						<div class="w-10 h-10 rounded-[10px] bg-violet-500/15 border border-violet-500/30 text-violet-400 flex items-center justify-center shrink-0">
							<svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
								<path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"/>
							</svg>
						</div>
						<div class="flex-1 min-w-0">
							<div class="text-white font-semibold text-sm font-mono truncate">{c.name}</div>
							<div class="text-[11px] text-gray-500 mt-0.5">오브젝트 {c.count}개</div>
						</div>
					</div>

					<!-- Stats -->
					<div class="grid grid-cols-2 gap-2 mb-3">
						<div>
							<div class="text-[11px] uppercase tracking-wider font-medium text-gray-500">오브젝트</div>
							<div class="text-white font-mono text-sm mt-0.5">{c.count}</div>
						</div>
						<div>
							<div class="text-[11px] uppercase tracking-wider font-medium text-gray-500">크기</div>
							<div class="text-white font-mono text-sm mt-0.5">{formatStorage(c.bytes / 1_000_000_000)}</div>
						</div>
					</div>

					<!-- Footer -->
					<div class="pt-3 border-t border-gray-800 flex items-center justify-between">
						<a
							href="/dashboard/object-storage/buckets/{encodeURIComponent(c.name)}"
							class="text-xs text-blue-400 hover:text-blue-300 transition-colors"
						>상세 보기 →</a>
						<button
							onclick={() => deleteContainer(c.name)}
							disabled={deleting === c.name}
							class="text-xs text-red-400 hover:text-red-300 disabled:text-gray-600 transition-colors"
						>{deleting === c.name ? '삭제 중...' : '삭제'}</button>
					</div>
				</div>
			{/each}
		</div>
	{/if}
</div>
