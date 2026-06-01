<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { toast } from '$lib/stores/toast';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import FormModal from '$lib/components/ui/FormModal.svelte';
	import { secretsApi } from '$lib/api/secrets';
	import { ApiError } from '$lib/api/client';
	import { untrack } from 'svelte';

	interface ProjectQuota {
		project_id: string;
		project_quotas: {
			secrets?: number;
			orders?: number;
			containers?: number;
			consumers?: number;
			cas?: number;
		};
	}

	let quotas = $state<ProjectQuota[]>([]);
	let loading = $state(true);
	let refreshing = $state(false);
	let error = $state('');

	// 쿼터 설정 모달
	let showSetQuota = $state(false);
	let editProjectId = $state('');
	let editSecrets = $state<number | null>(null);
	let editOrders = $state<number | null>(null);
	let editContainers = $state<number | null>(null);
	let submitting = $state(false);

	async function fetchQuotas() {
		try {
			quotas = (await secretsApi.listProjectQuotas($auth.token ?? undefined, $auth.projectId ?? undefined)) as ProjectQuota[];
			error = '';
		} catch (e) {
			error = e instanceof ApiError ? `조회 실패 (${e.status})` : '서버 오류';
		} finally {
			loading = false;
		}
	}

	async function forceRefresh() {
		refreshing = true;
		try { await fetchQuotas(); }
		finally { refreshing = false; }
	}

	const ar = createAutoRefresh(() => fetchQuotas(), {
		storageKey: 'admin-key-manager',
		defaultActive: false,
		defaultInterval: 60,
	});

	$effect(() => {
		const token = $auth.token;
		if (!token) return;
		untrack(() => fetchQuotas());
	});

	function openEdit(q: ProjectQuota) {
		editProjectId = q.project_id;
		editSecrets = q.project_quotas.secrets ?? null;
		editOrders = q.project_quotas.orders ?? null;
		editContainers = q.project_quotas.containers ?? null;
		showSetQuota = true;
	}

	async function handleSetQuota() {
		submitting = true;
		const body: Record<string, number> = {};
		if (editSecrets !== null) body.secrets = editSecrets;
		if (editOrders !== null) body.orders = editOrders;
		if (editContainers !== null) body.containers = editContainers;
		try {
			await secretsApi.setProjectQuota(editProjectId, body, $auth.token ?? undefined, $auth.projectId ?? undefined);
			toast.success('쿼터가 설정되었습니다');
			showSetQuota = false;
			await fetchQuotas();
		} catch (e) {
			toast.error('설정 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		} finally {
			submitting = false;
		}
	}

	async function handleResetQuota(projectId: string) {
		try {
			await secretsApi.deleteProjectQuota(projectId, $auth.token ?? undefined, $auth.projectId ?? undefined);
			toast.success('기본값으로 초기화되었습니다');
			await fetchQuotas();
		} catch (e) {
			toast.error('초기화 실패: ' + (e instanceof ApiError ? e.message : String(e)));
		}
	}

	type FieldEntry = [string, number | null, (v: number | null) => void];

	const quotaFields = $derived<FieldEntry[]>([
		['비밀 (secrets)', editSecrets, (v) => { editSecrets = v; }],
		['Orders', editOrders, (v) => { editOrders = v; }],
		['컨테이너', editContainers, (v) => { editContainers = v; }],
	]);
</script>

<FormModal
	bind:open={showSetQuota}
	title="프로젝트 쿼터 설정"
	submitLabel="저장"
	submitting={submitting}
	onSubmit={handleSetQuota}
	onClose={() => { showSetQuota = false; }}
>
	<div class="space-y-4">
		<div class="text-xs text-gray-400 font-mono">{editProjectId}</div>
		<p class="text-xs text-gray-500">-1 = 무제한, 0 = 비활성</p>
		{#each quotaFields as [label, val, setter]}
			<div>
				<label class="block text-sm text-gray-400 mb-1">{label}</label>
				<input
					type="number"
					value={val ?? ''}
					oninput={(e) => setter(e.currentTarget.value ? Number(e.currentTarget.value) : null)}
					class="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white"
					placeholder="-1 (무제한)"
				/>
			</div>
		{/each}
	</div>
</FormModal>

<div class="p-4 md:p-8">
	<PageHeader breadcrumb="ADMIN / KEY MANAGER" title="Key Manager 쿼터">
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

	{#if error}<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">{error}</div>{/if}

	{#if loading}
		<LoadingSkeleton variant="table" rows={4} />
	{:else if quotas.length === 0}
		<div class="text-center py-16 text-gray-500">
			<div class="text-4xl mb-3">📊</div>
			<p class="text-sm">설정된 프로젝트 쿼터가 없습니다. (모두 기본값 사용 중)</p>
		</div>
	{:else}
		<div class="overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="text-left text-gray-400 border-b border-gray-700">
						<th class="pb-3 pr-4 font-medium">프로젝트 ID</th>
						<th class="pb-3 pr-4 font-medium">Secrets</th>
						<th class="pb-3 pr-4 font-medium">Orders</th>
						<th class="pb-3 pr-4 font-medium">Containers</th>
						<th class="pb-3 font-medium">액션</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-gray-800">
					{#each quotas as q}
						<tr class="hover:bg-gray-800/30">
							<td class="py-3 pr-4 font-mono text-xs text-gray-300">{q.project_id}</td>
							<td class="py-3 pr-4 text-gray-300">{q.project_quotas.secrets ?? -1}</td>
							<td class="py-3 pr-4 text-gray-300">{q.project_quotas.orders ?? -1}</td>
							<td class="py-3 pr-4 text-gray-300">{q.project_quotas.containers ?? -1}</td>
							<td class="py-3 flex gap-3">
								<button onclick={() => openEdit(q)} class="text-xs text-blue-400 hover:text-blue-300">설정</button>
								<button onclick={() => handleResetQuota(q.project_id)} class="text-xs text-gray-400 hover:text-gray-200">초기화</button>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>
