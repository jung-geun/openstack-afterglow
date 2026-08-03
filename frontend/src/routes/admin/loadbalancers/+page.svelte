<script lang="ts">
	import { onMount } from 'svelte';
	import { auth } from '$lib/stores/auth';
	import { api, ApiError } from '$lib/api/client';
	import type { LoadBalancer } from '$lib/types/loadbalancer';
	import PageHeader from '$lib/components/ui/PageHeader.svelte';
	import AutoRefreshControl from '$lib/components/AutoRefreshControl.svelte';
	import SlidePanel from '$lib/components/SlidePanel.svelte';
	import LoadBalancerDetailPanel from '$lib/components/LoadBalancerDetailPanel.svelte';
	import { createAutoRefresh } from '$lib/utils/autoRefresh.svelte';

	let loadbalancers = $state<LoadBalancer[]>([]);
	let loading = $state(true);
	let error = $state('');
	let selectedLbId = $state<string | null>(null);

	const token = $derived($auth.token ?? undefined);
	const projectId = $derived($auth.projectId ?? undefined);

	async function fetchLoadbalancers(opts?: { refresh?: boolean }) {
		try {
			loadbalancers = await api.get<LoadBalancer[]>('/api/v1/admin/all-loadbalancers', token, projectId, opts);
			error = '';
		} catch (e) {
			error = e instanceof ApiError ? `조회 실패 (${e.status})` : '서버 오류';
		} finally {
			loading = false;
		}
	}

	const ar = createAutoRefresh(() => fetchLoadbalancers(), {
		storageKey: 'admin-loadbalancers',
		invokeOnMount: false,
		defaultInterval: 30,
		intervalOptions: [15, 30, 60]
	});

	function openLbPanel(id: string) {
		selectedLbId = id;
	}

	function closeLbPanel() {
		selectedLbId = null;
	}

	onMount(() => {
		fetchLoadbalancers();
	});
</script>

<div class="p-4 md:p-8 max-w-7xl mx-auto">
	<PageHeader breadcrumb="NETWORK / LOADBALANCERS" title="로드밸런서">
		{#snippet actions()}
			<AutoRefreshControl
				bind:active={ar.active}
				bind:intervalSeconds={ar.intervalSeconds}
				intervalOptions={ar.intervalOptions}
				refreshing={loading}
				onManualRefresh={() => fetchLoadbalancers({ refresh: true })}
			/>
		{/snippet}
	</PageHeader>

	{#if error}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">
			{error}
		</div>
	{/if}

	{#if loading && loadbalancers.length === 0}
		<div class="space-y-4 animate-pulse">
			{#each [1, 2, 3] as _}
				<div class="h-12 bg-gray-800/50 rounded-lg"></div>
			{/each}
		</div>
	{:else if loadbalancers.length === 0}
		<div class="text-center py-20 text-gray-600 bg-gray-900/20 border border-gray-800/50 rounded-2xl">
			<div class="text-5xl mb-4">⚖️</div>
			<p class="text-lg">로드밸런서가 없습니다</p>
		</div>
	{:else}
		<div class="overflow-x-auto bg-gray-900/20 border border-gray-800/50 rounded-2xl p-5">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b border-gray-800 text-gray-400 text-xs uppercase tracking-wide">
						<th class="text-left py-2 pr-4">이름 / ID</th>
						<th class="text-left py-2 pr-4">프로젝트 ID</th>
						<th class="text-left py-2 pr-4">VIP 주소</th>
						<th class="text-left py-2 pr-4">프로비저닝 상태</th>
						<th class="text-left py-2 pr-4">운영 상태</th>
						<th class="text-left py-2">액션</th>
					</tr>
				</thead>
				<tbody>
					{#each loadbalancers as lb (lb.id)}
						<tr class="border-b border-gray-800/30 text-xs transition-colors hover:bg-gray-800/10">
							<td class="p-0">
								<button
									type="button"
									onclick={() => openLbPanel(lb.id)}
									class="block w-full py-3 pr-4 font-semibold text-white hover:text-blue-400 transition-colors text-left"
									title={lb.name || lb.id}
								>
									<span class="max-md:block max-md:max-w-[40vw] max-md:truncate">
										{lb.name || lb.id.slice(0, 12)}
									</span>
								</button>
							</td>
							<td class="py-3 pr-4 text-gray-500 font-mono text-[10px] select-all" title={lb.project_id}>
								{lb.project_id ? lb.project_id.slice(0, 8) + '...' : '—'}
							</td>
							<td class="py-3 pr-4 text-gray-300 font-mono">
								{lb.vip_address ?? '—'}
							</td>
							<td class="py-3 pr-4 font-medium">
								<span class={lb.status === 'ACTIVE' ? 'text-green-400' : 'text-orange-400'}>
									{lb.status ?? '—'}
								</span>
							</td>
							<td class="py-3 pr-4">
								<span class={lb.operating_status === 'ONLINE' ? 'text-green-400' : lb.operating_status === 'OFFLINE' ? 'text-red-400' : 'text-gray-500'}>
									{lb.operating_status ?? '—'}
								</span>
							</td>
							<td class="py-3" onclick={(e) => e.stopPropagation()}>
								<button
									onclick={() => openLbPanel(lb.id)}
									class="px-2.5 py-1 text-xs bg-gray-800 hover:bg-gray-700 text-gray-300 border border-gray-700 rounded transition-colors"
								>
									상세
								</button>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
			<div class="mt-4 text-xs text-gray-500">총 {loadbalancers.length}개 로드밸런서</div>
		</div>
	{/if}
</div>

{#if selectedLbId}
	<SlidePanel onClose={closeLbPanel}>
		<LoadBalancerDetailPanel
			lbId={selectedLbId}
			onClose={closeLbPanel}
			onDeleted={() => {
				fetchLoadbalancers();
				closeLbPanel();
			}}
		/>
	</SlidePanel>
{/if}
