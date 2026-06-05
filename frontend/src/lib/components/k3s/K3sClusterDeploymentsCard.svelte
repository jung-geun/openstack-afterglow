<script lang="ts">
	import { untrack } from 'svelte';
	import { useK3sClusterDetailController } from '$lib/stores/k3sClusterDetailController.svelte';
	import { SectionHeader } from '$lib/components/ui';
	import K3sScaleModal from './K3sScaleModal.svelte';
	import type { DeploymentInfo } from '$lib/types/k3s';

	const s = useK3sClusterDetailController();

	let loading = $state(false);
	let loadError = $state('');
	let scalingDeploy = $state<DeploymentInfo | null>(null);

	$effect(() => {
		const ns = s.selectedNamespace;
		if (!ns) return;
		if (s.deploymentsLoaded) return;
		loading = true;
		loadError = '';
		untrack(() => s.loadDeployments())
			.catch(() => { loadError = 'Deployment 로드 실패'; })
			.finally(() => { loading = false; });
	});
</script>

{#if scalingDeploy}
	<K3sScaleModal
		deploymentName={scalingDeploy.name}
		currentReplicas={scalingDeploy.replicas}
		onClose={() => { scalingDeploy = null; }}
		onApply={(r) => s.scaleDeploymentTo(scalingDeploy!.name, r)}
	/>
{/if}

<!-- Deployments -->
<div class="bg-gray-900 border border-gray-800 rounded-2xl p-5 mb-4">
	<SectionHeader title="Deployment" meta="{s.deployments.length}개" />

	{#if loading}
		<div class="mt-4 text-sm text-gray-400 text-center py-6">로딩 중...</div>
	{:else if loadError}
		<div class="mt-4 text-sm text-red-400">{loadError}</div>
	{:else if s.deployments.length === 0}
		<div class="mt-4 text-sm text-gray-500 text-center py-6">Deployment 없음</div>
	{:else}
		<div class="mt-4 overflow-x-auto">
			<table class="w-full text-xs">
				<thead>
					<tr class="border-b border-gray-800">
						<th class="text-left pb-2 text-[10px] uppercase tracking-wide text-gray-500 font-medium">이름</th>
						<th class="text-left pb-2 text-[10px] uppercase tracking-wide text-gray-500 font-medium">레플리카</th>
						<th class="text-left pb-2 text-[10px] uppercase tracking-wide text-gray-500 font-medium">전략</th>
						<th class="text-left pb-2 text-[10px] uppercase tracking-wide text-gray-500 font-medium">이미지</th>
						<th class="pb-2"></th>
					</tr>
				</thead>
				<tbody>
					{#each s.deployments as dep}
						{@const actioning = s.workloadActioning === `${s.selectedNamespace}:deploy:${dep.name}`}
						<tr class="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
							<td class="py-2.5 text-white font-medium font-mono"><span class="max-md:block max-md:max-w-[66vw] max-md:truncate" title={dep.name}>{dep.name}</span></td>
							<td class="py-2.5">
								<span class="tabular-nums text-white">{dep.ready}/{dep.replicas}</span>
								{#if dep.available < dep.replicas}
									<span class="ml-1 text-yellow-400 text-[10px]">({dep.available} available)</span>
								{/if}
							</td>
							<td class="py-2.5 text-gray-400">{dep.strategy || '—'}</td>
							<td class="py-2.5 text-gray-400 max-w-[200px] truncate">{dep.images.join(', ') || '—'}</td>
							<td class="py-2.5 text-right">
								<div class="flex items-center justify-end gap-1.5">
									<button
										onclick={() => s.rolloutRestartDeployment(dep.name)}
										disabled={!!s.workloadActioning}
										class="px-2 py-1 rounded text-[10px] bg-blue-900/40 text-blue-300 hover:bg-blue-900/70 disabled:opacity-40 transition-colors"
									>{actioning ? '중...' : '재시작'}</button>
									<button
										onclick={() => { scalingDeploy = dep; }}
										disabled={!!s.workloadActioning}
										class="px-2 py-1 rounded text-[10px] bg-gray-800 text-gray-300 hover:bg-gray-700 disabled:opacity-40 transition-colors"
									>스케일</button>
								</div>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>

<!-- ReplicaSets -->
{#if s.replicasets.length > 0}
	<div class="bg-gray-900 border border-gray-800 rounded-2xl p-5 mb-4">
		<SectionHeader title="ReplicaSet" meta="{s.replicasets.length}개" />
		<div class="mt-4 overflow-x-auto">
			<table class="w-full text-xs">
				<thead>
					<tr class="border-b border-gray-800">
						<th class="text-left pb-2 text-[10px] uppercase tracking-wide text-gray-500 font-medium">이름</th>
						<th class="text-left pb-2 text-[10px] uppercase tracking-wide text-gray-500 font-medium">레플리카</th>
						<th class="text-left pb-2 text-[10px] uppercase tracking-wide text-gray-500 font-medium">Owner</th>
						<th class="text-left pb-2 text-[10px] uppercase tracking-wide text-gray-500 font-medium">이미지</th>
					</tr>
				</thead>
				<tbody>
					{#each s.replicasets as rs}
						<tr class="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors">
							<td class="py-2.5 text-gray-300 font-mono"><span class="max-md:block max-md:max-w-[66vw] max-md:truncate" title={rs.name}>{rs.name}</span></td>
							<td class="py-2.5 tabular-nums text-gray-300">{rs.ready}/{rs.replicas}</td>
							<td class="py-2.5 text-gray-400">
								{#if rs.owner_kind && rs.owner_name}
									<span class="text-[10px] bg-gray-800 px-1.5 py-0.5 rounded">{rs.owner_kind}</span>
									<span class="ml-1 font-mono">{rs.owner_name}</span>
								{:else}
									—
								{/if}
							</td>
							<td class="py-2.5 text-gray-400 max-w-[200px] truncate">{rs.images.join(', ') || '—'}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	</div>
{/if}
