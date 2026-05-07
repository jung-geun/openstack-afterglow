<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import { formatStorage } from '$lib/utils/format';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';

	interface SwiftContainer {
		name: string;
		count: number;
		bytes: number;
		project_id?: string;
		project_name?: string;
		is_quarantine?: boolean;
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
			api.get<SwiftContainer[]>('/api/object-storage?all_projects=true&include_quarantine=true', token, projectId)
				.then(v => { containers = v; loading = false; })
				.catch(() => { containers = []; loading = false; }),
			api.get<AccountMeta>('/api/object-storage/account', token, projectId)
				.then(v => { account = v; })
				.catch(() => {}),
		]);
		loading = false;
		refreshing = false;
	}

	async function createContainer() {
		if (!newName.trim()) return;
		creating = true;
		createError = '';
		try {
			await api.post('/api/object-storage', { name: newName.trim() }, token, projectId);
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

	const ar = createAutoRefresh(load, {
		storageKey: 'admin-object-storage',
		defaultActive: true,
		defaultInterval: 30,
		intervalOptions: [15, 30, 60]
	});

	onMount(load);
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
				<button onclick={() => { showModal = false; createError = ''; newName = ''; }}
					class="px-4 py-2 text-sm text-gray-400 hover:text-white border border-gray-700 rounded-lg transition-colors">취소</button>
				<button onclick={createContainer} disabled={creating || !newName.trim()}
					class="px-4 py-2 text-sm bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded-lg transition-colors">
					{creating ? '생성 중...' : '생성'}
				</button>
			</div>
		</div>
	</div>
{/if}

<div class="p-4 md:p-8 max-w-6xl">
	<PageHeader breadcrumb="STORAGE / OBJECT STORAGE" title="오브젝트 스토리지">
		{#snippet actions()}
			<button
				onclick={() => { showModal = true; createError = ''; newName = ''; }}
				class="text-xs text-white bg-indigo-600 hover:bg-indigo-500 transition-colors px-3 py-1.5 rounded border border-indigo-500"
			>+ 버킷 생성</button>
			<AutoRefreshControl
				bind:active={ar.active}
				bind:intervalSeconds={ar.intervalSeconds}
				intervalOptions={ar.intervalOptions}
				refreshing={loading || refreshing}
				onManualRefresh={load}
			/>
		{/snippet}
	</PageHeader>

	{#if account}
		<div class="grid grid-cols-3 gap-4 mb-6">
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
				<div class="text-xs text-gray-500 uppercase tracking-wide mb-1">버킷</div>
				<div class="text-2xl font-bold text-white">{account.container_count}</div>
			</div>
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
				<div class="text-xs text-gray-500 uppercase tracking-wide mb-1">오브젝트</div>
				<div class="text-2xl font-bold text-white">{account.object_count}</div>
			</div>
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
				<div class="text-xs text-gray-500 uppercase tracking-wide mb-1">사용 용량</div>
				<div class="text-2xl font-bold text-white">{formatStorage(account.bytes_used / 1_000_000_000)}</div>
			</div>
		</div>
	{/if}

	{#if loading}
		<LoadingSkeleton variant="table" rows={5} />
	{:else if containers.length === 0}
		<div class="text-gray-600 text-sm">버킷가 없습니다</div>
	{:else}
		<div class="overflow-x-auto" class:opacity-60={refreshing} class:pointer-events-none={refreshing}>
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
						<th class="text-left py-3 px-4 font-medium">버킷 이름</th>
						<th class="text-left py-3 px-4 font-medium">프로젝트</th>
						<th class="text-left py-3 px-4 font-medium">오브젝트 수</th>
						<th class="text-left py-3 px-4 font-medium">용량</th>
						<th class="text-right py-3 px-4 font-medium">액션</th>
					</tr>
				</thead>
				<tbody>
					{#each containers as c}
						<tr class="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors {c.is_quarantine ? 'bg-amber-950/20' : ''}">
							<td class="py-3 px-4">
								<a
									href="/admin/object-storage/{encodeURIComponent(c.name)}"
									class="text-indigo-400 hover:text-indigo-300 font-medium"
								>{c.name}</a>
								{#if c.is_quarantine}
									<span
										class="ml-2 inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] font-medium rounded border border-amber-800 bg-amber-950/50 text-amber-400"
										title="업로드 검증 중인 파일이 임시로 격리되는 시스템 버킷입니다. 검증 통과 시 원본 버킷으로 자동 이동됩니다."
									>
										격리용
									</span>
								{/if}
							</td>
							<td class="py-3 px-4 text-gray-400 text-xs font-mono">
								{c.project_name || c.project_id?.slice(0, 8) || '—'}
							</td>
							<td class="py-3 px-4 text-gray-300">{c.count}</td>
							<td class="py-3 px-4 text-gray-300">{formatStorage(Math.round(c.bytes / 1073741824))}</td>
							<td class="py-3 px-4 text-right">
								<button
									onclick={(e) => { e.stopPropagation(); deleteContainer(c.name); }}
									disabled={deleting === c.name}
									class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-xs px-2 py-1 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors"
								>{deleting === c.name ? '삭제 중...' : '삭제'}</button>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
		{#if containers.some((c) => c.is_quarantine)}
			<div class="mt-4 px-4 py-3 text-xs text-amber-400/80 bg-amber-950/20 border border-amber-900/50 rounded-lg">
				<strong class="text-amber-400">격리용 버킷 안내:</strong>
				<code>*-quarantine</code> 버킷은 사용자가 업로드한 파일이 검증 단계 동안 임시 저장되는 시스템 영역입니다.
				정상 업로드 시 원본 버킷으로 자동 이동되어 비워지지만, 검증 실패·취소·중단으로 객체가 남을 수 있습니다.
				필요 시 직접 삭제할 수 있습니다.
			</div>
		{/if}
	{/if}
</div>
