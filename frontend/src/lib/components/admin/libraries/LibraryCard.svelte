<script lang="ts">
	import StatusChip from '$lib/components/ui/StatusChip.svelte';
	import type { LibraryConfig } from '$lib/types/libraries';

	let {
		lib,
		buildStatus,
		latestMount,
		isBuilding,
		onTriggerBuild,
	}: {
		lib: LibraryConfig;
		buildStatus: string;
		latestMount?: number;
		isBuilding: boolean;
		onTriggerBuild: (lib: LibraryConfig) => void;
	} = $props();
</script>

<div id="lib-card-{lib.id}" class="bg-gray-800 rounded-lg border border-gray-700 p-5 flex flex-col gap-4">
	<div class="flex items-start justify-between">
		<div>
			<h3 class="font-semibold text-gray-100">{lib.name}</h3>
			<p class="text-xs text-gray-500 mt-0.5">v{lib.version}</p>
		</div>
		<div class="flex flex-col items-end gap-1">
			<StatusChip status={buildStatus} />
			<div class="flex items-center gap-1 flex-wrap justify-end">
				<span class="text-xs text-gray-600">{lib.share_proto ?? 'CEPHFS'}</span>
				<span class="px-1.5 py-0.5 text-xs rounded {lib.visibility === 'private' ? 'bg-gray-700 text-gray-400' : 'bg-green-900/30 text-green-500'}">
					{lib.visibility === 'private' ? '비공개' : '공개'}
				</span>
				{#if lib.license_type}
					<span class="px-1.5 py-0.5 text-xs rounded {lib.license_type === 'commercial' ? 'bg-amber-900/40 text-amber-400' : 'bg-blue-900/40 text-blue-400'}">
						{lib.license_type}
					</span>
				{/if}
			</div>
		</div>
	</div>

	{#if lib.depends_on && lib.depends_on.length > 0}
		<div>
			<p class="text-xs text-gray-500 mb-1.5">의존성</p>
			<div class="flex flex-wrap gap-1">
				{#each lib.depends_on as dep}
					<span class="px-2 py-0.5 text-xs bg-gray-700 text-gray-300 rounded-full">{dep}</span>
				{/each}
			</div>
		</div>
	{/if}

	{#if lib.packages && lib.packages.length > 0}
		<div>
			<p class="text-xs text-gray-500 mb-1.5">패키지 ({lib.packages.length})</p>
			<div class="flex flex-wrap gap-1">
				{#each lib.packages.slice(0, 5) as pkg}
					<span class="px-2 py-0.5 text-xs bg-gray-700/50 text-gray-400 rounded">{pkg}</span>
				{/each}
				{#if lib.packages.length > 5}
					<span class="px-2 py-0.5 text-xs text-gray-600">+{lib.packages.length - 5}개</span>
				{/if}
			</div>
		</div>
	{/if}

	{#if (lib.max_concurrent_mounts !== undefined && lib.max_concurrent_mounts !== null) || latestMount !== undefined}
		<div class="flex items-center gap-3 text-xs text-gray-500">
			{#if lib.max_concurrent_mounts !== undefined && lib.max_concurrent_mounts !== null}
				<span>최대 마운트: <span class="text-gray-300">{lib.max_concurrent_mounts}개</span></span>
			{:else}
				<span>최대 마운트: <span class="text-gray-300">무제한</span></span>
			{/if}
			{#if latestMount !== undefined}
				<span>현재 활성: <span class="text-green-400">{latestMount}개</span></span>
			{/if}
		</div>
	{/if}

	<div class="mt-auto pt-3 border-t border-gray-700">
		<button
			onclick={() => onTriggerBuild(lib)}
			disabled={isBuilding || buildStatus === 'building'}
			class="w-full py-1.5 text-sm bg-blue-700 hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed rounded-md transition-colors"
		>
			{isBuilding ? '요청 중...' : buildStatus === 'building' ? '빌드 중...' : buildStatus === 'ready' ? '재빌드' : '빌드 시작'}
		</button>
	</div>
</div>
