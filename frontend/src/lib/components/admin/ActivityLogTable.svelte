<script lang="ts">
	import { auth } from '$lib/stores/auth';
	import { api } from '$lib/api/client';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import StatusChip from '$lib/components/ui/StatusChip.svelte';

	interface Props {
		endpoint: string;
		storageKey: string;
		showUser?: boolean;
	}

	let { endpoint, storageKey, showUser = false }: Props = $props();

	interface ActivityLog {
		id: number;
		created_at: string;
		project_id: string;
		user_id: string;
		username: string;
		resource_type: string;
		resource_id: string | null;
		resource_name: string | null;
		action: string;
		status: 'success' | 'failed' | 'started';
		error_message: string | null;
		extra: Record<string, unknown> | null;
	}

	const PAGE = 50;

	let logs = $state<ActivityLog[]>([]);
	let loading = $state(true);
	let loadingMore = $state(false);
	let hasMore = $state(false);

	let filterResourceType = $state('');
	let filterAction = $state('');
	let filterUserId = $state('');

	let refreshing = $state(false);
	let expandedId = $state<number | null>(null);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function load(reset = true) {
		if (reset) { loading = true; logs = []; }
		else refreshing = true;
		const params: Record<string, string> = { limit: String(PAGE) };
		if (filterResourceType) params.resource_type = filterResourceType;
		if (filterAction) params.action = filterAction;
		if (showUser && filterUserId) params.user_id = filterUserId;
		const qs = new URLSearchParams(params).toString();
		try {
			const data = await api.get<ActivityLog[]>(`${endpoint}?${qs}`, token, projectId);
			logs = data;
			hasMore = data.length === PAGE;
		} catch {
			logs = [];
		} finally {
			loading = false;
			refreshing = false;
		}
	}

	async function loadMore() {
		if (!hasMore || loadingMore || logs.length === 0) return;
		loadingMore = true;
		const lastId = logs[logs.length - 1].id;
		const params: Record<string, string> = { limit: String(PAGE), before_id: String(lastId) };
		if (filterResourceType) params.resource_type = filterResourceType;
		if (filterAction) params.action = filterAction;
		if (showUser && filterUserId) params.user_id = filterUserId;
		const qs = new URLSearchParams(params).toString();
		try {
			const data = await api.get<ActivityLog[]>(`${endpoint}?${qs}`, token, projectId);
			logs = [...logs, ...data];
			hasMore = data.length === PAGE;
		} catch {
			// ignore
		} finally {
			loadingMore = false;
		}
	}

	const ar = createAutoRefresh(() => load(), {
		storageKey,
		defaultActive: true,
		defaultInterval: 30,
		intervalOptions: [15, 30, 60],
	});

	$effect(() => {
		// re-load when auth or filters change
		void $auth.projectId;
		load();
	});

	function relativeTime(iso: string): string {
		const diff = Date.now() - new Date(iso).getTime();
		const s = Math.floor(diff / 1000);
		if (s < 60) return `${s}초 전`;
		const m = Math.floor(s / 60);
		if (m < 60) return `${m}분 전`;
		const h = Math.floor(m / 60);
		if (h < 24) return `${h}시간 전`;
		return `${Math.floor(h / 24)}일 전`;
	}


	const RESOURCE_TYPES = [
		'instance', 'keypair', 'volume', 'volume_snapshot', 'volume_backup',
		'file_storage', 'share_snapshot', 'share_network', 'security_service',
		'network', 'subnet', 'router', 'floating_ip', 'security_group', 'load_balancer',
		'lb_listener', 'lb_pool', 'lb_member', 'lb_health_monitor',
		'k3s_cluster', 'container', 'container_cluster', 'library', 'union_layer',
	];
</script>

<div class="space-y-4">
	<!-- 필터 + 자동갱신 -->
	<div class="flex flex-wrap gap-3 items-center">
		<select
			bind:value={filterResourceType}
			onchange={() => load()}
			class="bg-gray-800 border border-gray-600 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:border-blue-500"
		>
			<option value="">전체 리소스</option>
			{#each RESOURCE_TYPES as rt}
				<option value={rt}>{rt}</option>
			{/each}
		</select>
		<input
			bind:value={filterAction}
			oninput={() => load()}
			type="text"
			placeholder="액션 필터 (예: instance.create)"
			class="bg-gray-800 border border-gray-600 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:border-blue-500 w-52"
		/>
		{#if showUser}
			<input
				bind:value={filterUserId}
				oninput={() => load()}
				type="text"
				placeholder="사용자 ID"
				class="bg-gray-800 border border-gray-600 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:border-blue-500 w-44"
			/>
		{/if}
		<div class="ml-auto">
			<AutoRefreshControl
				bind:active={ar.active}
				bind:intervalSeconds={ar.intervalSeconds}
				intervalOptions={ar.intervalOptions}
				{refreshing}
				onManualRefresh={() => load()}
			/>
		</div>
	</div>

	<!-- 테이블 -->
	{#if loading}
		<div class="text-gray-400 text-sm py-8 text-center">로딩 중...</div>
	{:else if logs.length === 0}
		<div class="text-gray-500 text-sm py-8 text-center">활동 없음</div>
	{:else}
		<div class="overflow-x-auto rounded-lg border border-gray-800">
			<table class="w-full text-sm">
				<thead class="bg-gray-900 text-gray-400 text-xs uppercase tracking-wide">
					<tr>
						<th class="px-4 py-3 text-left font-medium">시각</th>
						{#if showUser}<th class="px-4 py-3 text-left font-medium">사용자</th>{/if}
						<th class="px-4 py-3 text-left font-medium">리소스</th>
						<th class="px-4 py-3 text-left font-medium">액션</th>
						<th class="px-4 py-3 text-left font-medium">상태</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-gray-800">
					{#each logs as log (log.id)}
						<tr class="hover:bg-gray-800/40 transition-colors">
							<td class="px-4 py-3 text-gray-300 whitespace-nowrap" title={log.created_at}>
								{relativeTime(log.created_at)}
							</td>
							{#if showUser}
								<td class="px-4 py-3 text-gray-300">{log.username}</td>
							{/if}
							<td class="px-4 py-3 text-gray-300">
								<span class="text-gray-400 text-xs">{log.resource_type}</span>
								{#if log.resource_name}
									<span class="ml-1 text-white">{log.resource_name}</span>
								{:else if log.resource_id}
									<span class="ml-1 font-mono text-xs text-gray-400">{log.resource_id.slice(0, 8)}</span>
								{/if}
							</td>
							<td class="px-4 py-3 font-mono text-xs text-gray-300">{log.action}</td>
							<td class="px-4 py-3">
								<div class="flex items-center gap-2">
									<StatusChip status={log.status} />
									{#if log.status === 'failed' && log.error_message}
										<button
											onclick={() => expandedId = expandedId === log.id ? null : log.id}
											class="text-gray-500 hover:text-gray-300 text-xs underline"
										>
											{expandedId === log.id ? '닫기' : '상세'}
										</button>
									{/if}
								</div>
								{#if expandedId === log.id && log.error_message}
									<div class="mt-2 text-xs text-red-400 bg-red-950/30 border border-red-900/40 rounded px-2 py-1.5 max-w-xs break-words">
										{log.error_message}
									</div>
								{/if}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>

		{#if hasMore}
			<div class="text-center pt-2">
				<button
					onclick={loadMore}
					disabled={loadingMore}
					class="px-4 py-2 text-sm text-gray-400 hover:text-white border border-gray-700 hover:border-gray-500 rounded-lg transition-colors disabled:opacity-50"
				>
					{loadingMore ? '로딩 중...' : '더 보기'}
				</button>
			</div>
		{/if}
	{/if}
</div>
