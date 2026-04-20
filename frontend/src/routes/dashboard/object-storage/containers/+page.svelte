<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import { formatStorage } from '$lib/utils/format';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';

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
	let deleting = $state<string | null>(null);

	// 생성 모달
	let showModal = $state(false);
	let creating = $state(false);
	let createError = $state('');
	let newName = $state('');

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function load() {
		loading = true;
		try {
			[containers, account] = await Promise.all([
				api.get<SwiftContainer[]>('/api/object-storage', token, projectId),
				api.get<AccountMeta>('/api/object-storage/account', token, projectId),
			]);
		} catch {
			containers = [];
		} finally {
			loading = false;
		}
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
			createError = e instanceof ApiError ? e.message : '컨테이너 생성 실패';
		} finally {
			creating = false;
		}
	}

	async function deleteContainer(name: string) {
		if (!confirm(`컨테이너 "${name}"를 삭제하시겠습니까? 비어있어야 삭제됩니다.`)) return;
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
			<h2 class="text-lg font-semibold text-white mb-4">컨테이너 생성</h2>
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

<div class="p-4 md:p-8 max-w-6xl">
	<PageHeader breadcrumb="OBJECT STORAGE / CONTAINERS" title="컨테이너">
		{#snippet actions()}
			<button
				onclick={() => { showModal = true; createError = ''; newName = ''; }}
				class="text-xs text-white bg-indigo-600 hover:bg-indigo-500 transition-colors px-3 py-1.5 rounded border border-indigo-500"
			>+ 컨테이너 생성</button>
			<button onclick={load} class="text-xs text-gray-400 hover:text-white transition-colors px-3 py-1.5 rounded border border-gray-700 hover:border-gray-600">새로고침</button>
		{/snippet}
	</PageHeader>

	{#if account}
		<div class="grid grid-cols-3 gap-4 mb-6">
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
				<div class="text-xs text-gray-500 uppercase tracking-wide mb-1">컨테이너</div>
				<div class="text-2xl font-bold text-white">{account.container_count}</div>
			</div>
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
				<div class="text-xs text-gray-500 uppercase tracking-wide mb-1">오브젝트</div>
				<div class="text-2xl font-bold text-white">{account.object_count}</div>
			</div>
			<div class="bg-gray-900 border border-gray-800 rounded-xl p-4">
				<div class="text-xs text-gray-500 uppercase tracking-wide mb-1">사용 용량</div>
				<div class="text-2xl font-bold text-white">{formatStorage(Math.round(account.bytes_used / 1073741824))}</div>
			</div>
		</div>
	{/if}

	{#if loading}
		<LoadingSkeleton variant="table" rows={5} />
	{:else if containers.length === 0}
		<div class="text-gray-600 text-sm">컨테이너가 없습니다</div>
	{:else}
		<div class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
						<th class="text-left py-3 px-4 font-medium">컨테이너 이름</th>
						<th class="text-left py-3 px-4 font-medium">오브젝트 수</th>
						<th class="text-left py-3 px-4 font-medium">용량</th>
						<th class="text-right py-3 px-4 font-medium">액션</th>
					</tr>
				</thead>
				<tbody>
					{#each containers as c}
						<tr class="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
							<td class="py-3 px-4">
								<a
									href="/dashboard/object-storage/containers/{encodeURIComponent(c.name)}"
									class="text-indigo-400 hover:text-indigo-300 font-medium"
								>{c.name}</a>
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
	{/if}
</div>
