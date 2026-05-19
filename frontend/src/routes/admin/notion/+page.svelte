<script lang="ts">
	import { confirmDialog } from '$lib/stores/confirm.svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import { env } from '$env/dynamic/public';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import NotionTargetAddForm from '$lib/components/admin/notion/NotionTargetAddForm.svelte';
	import NotionTargetEditForm from '$lib/components/admin/notion/NotionTargetEditForm.svelte';
	import NotionTargetCard from '$lib/components/admin/notion/NotionTargetCard.svelte';
	import type { NotionTarget } from '$lib/components/admin/notion/NotionTargetCard.svelte';

	function getBaseUrl(): string {
		if (typeof window !== 'undefined') {
			return env.PUBLIC_API_BASE || `${window.location.protocol}//${window.location.hostname}:8000`;
		}
		return env.PUBLIC_API_BASE || 'http://backend:8000';
	}

	let targets = $state<NotionTarget[]>([]);
	let loading = $state(true);
	let error = $state('');
	let showAddForm = $state(false);
	let editingTarget = $state<NotionTarget | null>(null);
	let testingId = $state<number | null>(null);
	let testMessages = $state<Record<number, string>>({});
	let testErrors = $state<Record<number, string>>({});

	async function fetchTargets() {
		loading = true;
		try {
			targets = await api.get<NotionTarget[]>(
				'/api/admin/notion/targets',
				$auth.token ?? undefined,
				$auth.projectId ?? undefined
			);
			error = '';
		} catch (e) {
			error = e instanceof ApiError ? `조회 실패 (${e.status})` : '서버 오류';
		} finally {
			loading = false;
		}
	}

	async function deleteTarget(id: number) {
		if (!await confirmDialog('이 연동 대상을 삭제하시겠습니까?')) return;
		try {
			await api.delete(
				`/api/admin/notion/targets/${id}`,
				$auth.token ?? undefined,
				$auth.projectId ?? undefined
			);
			await fetchTargets();
		} catch {
			alert('삭제 실패');
		}
	}

	async function testTarget(id: number) {
		testingId = id;
		testMessages = { ...testMessages, [id]: '' };
		testErrors = { ...testErrors, [id]: '' };
		try {
			const headers: Record<string, string> = { 'Content-Type': 'application/json' };
			if ($auth.token) headers['Authorization'] = `Bearer ${$auth.token}`;
			if ($auth.projectId) headers['X-Project-Id'] = $auth.projectId;
			const resp = await fetch(`${getBaseUrl()}/api/admin/notion/targets/${id}/test`, {
				method: 'POST',
				headers,
				body: '{}',
				signal: AbortSignal.timeout(120_000),
			});
			if (!resp.ok) {
				const body = await resp.json().catch(() => ({ detail: resp.statusText }));
				throw new ApiError(resp.status, body?.detail || resp.statusText);
			}
			const result = await resp.json();
			testMessages = { ...testMessages, [id]: result.message };
			await fetchTargets();
		} catch (e) {
			testErrors = {
				...testErrors,
				[id]: e instanceof ApiError
					? e.message
					: (e instanceof Error && e.name === 'TimeoutError')
						? '동기화 시간 초과 (2분)'
						: '테스트 실패',
			};
		} finally {
			testingId = null;
		}
	}

	$effect(() => {
		if ($auth.token) fetchTargets();
	});
</script>

<div class="p-4 md:p-8 max-w-3xl">
	<PageHeader breadcrumb="SYSTEM / NOTION" title="Notion 연동" subtitle="OpenStack 리소스를 여러 Notion DB에 동시에 동기화합니다.">
		{#snippet actions()}
			<button
				onclick={() => { showAddForm = !showAddForm; }}
				class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-colors"
			>
				{showAddForm ? '취소' : '+ 연결 추가'}
			</button>
		{/snippet}
	</PageHeader>

	{#if error}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>
	{/if}

	<NotionTargetAddForm bind:open={showAddForm} onAdded={fetchTargets} />

	{#if loading}
		<div class="space-y-3">
			{#each [0, 1] as _}
				<div class="animate-pulse bg-gray-900 rounded-lg h-32"></div>
			{/each}
		</div>
	{:else if targets.length === 0}
		<div class="bg-gray-900 border border-gray-800 rounded-lg p-8 text-center">
			<p class="text-gray-500 text-sm">등록된 Notion 연동 대상이 없습니다.</p>
			<p class="text-gray-600 text-xs mt-1">"연결 추가" 버튼을 눌러 시작하세요.</p>
		</div>
	{:else}
		<div class="space-y-4">
			{#each targets as target (target.id)}
				<div class="bg-gray-900 border border-gray-800 rounded-lg p-5">
					{#if editingTarget?.id === target.id}
						<NotionTargetEditForm
							{target}
							onClose={() => (editingTarget = null)}
							onSaved={fetchTargets}
						/>
					{:else}
						<NotionTargetCard
							{target}
							testing={testingId === target.id}
							testMessage={testMessages[target.id] ?? ''}
							testError={testErrors[target.id] ?? ''}
							onTest={() => testTarget(target.id)}
							onEdit={() => (editingTarget = target)}
							onDelete={() => deleteTarget(target.id)}
						/>
					{/if}
				</div>
			{/each}
		</div>
	{/if}

	<div class="mt-6 bg-gray-900 border border-gray-800 rounded-lg p-5">
		<h3 class="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-2">설정 방법</h3>
		<ol class="text-xs text-gray-500 space-y-1.5 list-decimal list-inside">
			<li>
				<a href="https://www.notion.so/profile/integrations" target="_blank" class="text-blue-500 hover:text-blue-400">Notion Integrations</a>에서 Internal Integration 생성
			</li>
			<li>Notion에서 빈 Database 페이지 생성 후 Integration 연결 추가</li>
			<li>Database URL에서 32자리 ID 복사</li>
			<li>"연결 추가" 버튼으로 등록 — 필요한 컬럼이 자동 생성됩니다</li>
			<li>여러 연동 대상을 등록하면 동일한 데이터를 각 Notion DB에 동시에 동기화합니다</li>
		</ol>
	</div>
</div>
