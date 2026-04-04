<script lang="ts">
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';

	interface Share {
		id: string;
		name: string;
		status: string;
		size: number;
		share_proto: string;
		export_locations: string[];
		metadata: Record<string, string>;
		library_name: string | null;
		library_version: string | null;
		built_at: string | null;
	}

	let share = $state<Share | null>(null);
	let loading = $state(true);
	let error = $state('');
	let copiedIndex = $state<number | null>(null);
	let deleting = $state(false);

	const statusColor: Record<string, string> = {
		available: 'text-green-400 bg-green-900/30',
		creating: 'text-yellow-400 bg-yellow-900/30',
		deleting: 'text-orange-400 bg-orange-900/30',
		error: 'text-red-400 bg-red-900/30',
	};

	$effect(() => {
		const id = $page.params.id;
		if (!id || !$auth.token) return;
		fetchShare(id);
	});

	async function fetchShare(id: string) {
		loading = true;
		error = '';
		try {
			share = await api.get<Share>(
				`/api/shares/${id}`,
				$auth.token ?? undefined,
				$auth.projectId ?? undefined
			);
		} catch (e) {
			error = e instanceof ApiError ? `조회 실패 (${e.status}): ${e.message}` : '서버 오류';
		} finally {
			loading = false;
		}
	}

	async function copyPath(path: string, index: number) {
		await navigator.clipboard.writeText(path);
		copiedIndex = index;
		setTimeout(() => (copiedIndex = null), 2000);
	}

	async function deleteShare() {
		if (!share) return;
		if (!confirm(`Share "${share.name || share.id}"를 삭제하시겠습니까?`)) return;
		deleting = true;
		try {
			await api.delete(`/api/shares/${share.id}`, $auth.token ?? undefined, $auth.projectId ?? undefined);
			goto('/dashboard');
		} catch (e) {
			alert('삭제 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			deleting = false;
		}
	}
</script>

<div class="p-8 max-w-4xl mx-auto">
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
	{:else if share}
		<div class="flex items-start justify-between mb-6">
			<div>
				<h1 class="text-2xl font-bold text-white">{share.name || share.id}</h1>
				<div class="flex items-center gap-2 mt-2">
					<span
						class="px-2 py-0.5 rounded text-xs font-medium {statusColor[share.status] ?? 'text-gray-400 bg-gray-800'}"
					>
						{share.status}
					</span>
					<span class="px-1.5 py-0.5 bg-purple-900/40 text-purple-300 rounded text-xs">
						{share.share_proto}
					</span>
				</div>
			</div>
			<button
				onclick={deleteShare}
				disabled={deleting}
				class="text-red-400 hover:text-red-300 disabled:text-gray-600 text-sm px-3 py-1.5 rounded border border-red-900 hover:border-red-700 disabled:border-gray-700 transition-colors"
			>
				{deleting ? '삭제 중...' : '삭제'}
			</button>
		</div>

		<!-- 기본 정보 -->
		<div class="bg-gray-900 border border-gray-800 rounded-lg p-6 mb-4">
			<h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-4">기본 정보</h2>
			<dl class="grid grid-cols-2 gap-x-8 gap-y-3">
				<div>
					<dt class="text-xs text-gray-500 mb-0.5">ID</dt>
					<dd class="text-sm text-gray-300 font-mono">{share.id}</dd>
				</div>
				<div>
					<dt class="text-xs text-gray-500 mb-0.5">크기</dt>
					<dd class="text-sm text-gray-300">{share.size} GB</dd>
				</div>
				{#if share.library_name}
					<div>
						<dt class="text-xs text-gray-500 mb-0.5">라이브러리</dt>
						<dd class="text-sm text-gray-300">{share.library_name}</dd>
					</div>
					<div>
						<dt class="text-xs text-gray-500 mb-0.5">버전</dt>
						<dd class="text-sm text-gray-300">{share.library_version ?? '-'}</dd>
					</div>
					{#if share.built_at}
						<div class="col-span-2">
							<dt class="text-xs text-gray-500 mb-0.5">빌드 일시</dt>
							<dd class="text-sm text-gray-300">{share.built_at}</dd>
						</div>
					{/if}
				{/if}
			</dl>
		</div>

		<!-- Export Locations -->
		{#if share.export_locations.length > 0}
			<div class="bg-gray-900 border border-gray-800 rounded-lg p-6 mb-4">
				<h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-4">
					Export Locations
				</h2>
				<div class="space-y-2">
					{#each share.export_locations as path, i}
						<div class="flex items-center gap-2">
							<code
								class="flex-1 text-xs text-gray-300 bg-gray-800 px-3 py-2 rounded font-mono break-all"
							>
								{path}
							</code>
							<button
								onclick={() => copyPath(path, i)}
								class="shrink-0 text-xs px-2 py-1.5 rounded border transition-colors {copiedIndex === i
									? 'border-green-700 text-green-400'
									: 'border-gray-700 text-gray-400 hover:text-gray-200 hover:border-gray-500'}"
							>
								{copiedIndex === i ? '복사됨' : '복사'}
							</button>
						</div>
					{/each}
				</div>
			</div>
		{/if}

		<!-- 메타데이터 -->
		{#if Object.keys(share.metadata).length > 0}
			<div class="bg-gray-900 border border-gray-800 rounded-lg p-6">
				<h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-4">메타데이터</h2>
				<table class="w-full text-sm">
					<tbody>
						{#each Object.entries(share.metadata) as [k, v]}
							<tr class="border-b border-gray-800/50">
								<td class="py-2 pr-4 text-gray-500 text-xs w-1/3">{k}</td>
								<td class="py-2 text-gray-300 font-mono text-xs break-all">{v}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	{/if}
</div>
