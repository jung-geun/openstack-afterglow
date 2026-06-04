<script lang="ts">
	import { untrack } from 'svelte';
	import { useK3sClusterDetailController } from '$lib/stores/k3sClusterDetailController.svelte';
	import { SectionHeader } from '$lib/components/ui';

	const s = useK3sClusterDetailController();

	let loading = $state(false);
	let loadError = $state('');

	$effect(() => {
		const ns = s.selectedNamespace;
		if (!ns) return;
		if (s.servicesLoaded) return;
		loading = true;
		loadError = '';
		untrack(() => s.loadServices())
			.catch(() => { loadError = 'Service 로드 실패'; })
			.finally(() => { loading = false; });
	});
</script>

<div class="bg-gray-900 border border-gray-800 rounded-2xl p-5 mb-4">
	<SectionHeader title="Service" meta="{s.services.length}개" />

	{#if loading}
		<div class="mt-4 text-sm text-gray-400 text-center py-6">로딩 중...</div>
	{:else if loadError}
		<div class="mt-4 text-sm text-red-400">{loadError}</div>
	{:else if s.services.length === 0}
		<div class="mt-4 text-sm text-gray-500 text-center py-6">Service 없음</div>
	{:else}
		<div class="mt-4 overflow-x-auto">
			<table class="w-full text-xs">
				<thead>
					<tr class="border-b border-gray-800">
						<th class="text-left pb-2 text-[10px] uppercase tracking-wide text-gray-500 font-medium">이름</th>
						<th class="text-left pb-2 text-[10px] uppercase tracking-wide text-gray-500 font-medium">타입</th>
						<th class="text-left pb-2 text-[10px] uppercase tracking-wide text-gray-500 font-medium">Cluster IP</th>
						<th class="text-left pb-2 text-[10px] uppercase tracking-wide text-gray-500 font-medium">포트</th>
						<th class="text-left pb-2 text-[10px] uppercase tracking-wide text-gray-500 font-medium">생성일</th>
						<th class="pb-2"></th>
					</tr>
				</thead>
				<tbody>
					{#each s.services as svc}
						{@const actioning = s.workloadActioning === `${s.selectedNamespace}:svc:${svc.name}`}
						<tr class="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
							<td class="py-2.5 text-white font-medium font-mono">{svc.name}</td>
							<td class="py-2.5 text-gray-400">{svc.type}</td>
							<td class="py-2.5 text-gray-400 font-mono">{svc.cluster_ip ?? '—'}</td>
							<td class="py-2.5 text-gray-400">
								{svc.ports.map(p => `${p.port}${p.node_port ? ':' + p.node_port : ''}/${p.protocol}`).join(', ') || '—'}
							</td>
							<td class="py-2.5 text-gray-500">{svc.created_at ? svc.created_at.slice(0, 10) : '—'}</td>
							<td class="py-2.5 text-right">
								<button
									onclick={() => s.removeSvc(svc.name)}
									disabled={!!s.workloadActioning}
									class="px-2 py-1 rounded text-[10px] bg-red-900/40 text-red-300 hover:bg-red-900/70 disabled:opacity-40 transition-colors"
								>
									{actioning ? '삭제 중...' : '삭제'}
								</button>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>
