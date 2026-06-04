<script lang="ts">
	import type { GpuType } from '$lib/types/gpu';

	let {
		gpuTypes,
		selectedGpuTypes = $bindable(),
		onToggle,
	}: {
		gpuTypes: GpuType[];
		selectedGpuTypes: Set<string>;
		onToggle: (deviceName: string) => void;
	} = $props();
</script>

{#if gpuTypes.length > 0}
	<div class="mb-6">
		<div class="text-xs text-gray-400 uppercase tracking-wide mb-2">GPU 종류별 현황</div>
		<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
			{#each gpuTypes as gt}
				<button
					onclick={() => onToggle(gt.device_name)}
					class="bg-gray-900 border rounded-lg px-4 py-3 flex items-center justify-between text-left transition-colors {selectedGpuTypes.has(gt.device_name) ? 'border-blue-500 bg-blue-900/20' : 'border-gray-800 hover:border-gray-600'}"
				>
					<div>
						<div class="text-sm font-medium text-white flex items-center gap-1.5">
							{gt.device_name}
							{#if selectedGpuTypes.has(gt.device_name)}
								<span class="text-xs bg-blue-600 text-white px-1 rounded">선택됨</span>
							{/if}
						</div>
						<div class="text-xs text-gray-500">{gt.vendor}</div>
					</div>
					<div class="text-right">
						<div class="text-sm font-semibold text-white">{gt.total}</div>
						{#if gt.used > 0}
							<div class="text-xs text-red-400">{gt.used} 사용 중</div>
						{/if}
						{#if gt.total - gt.used > 0}
							<div class="text-xs text-green-400">{gt.total - gt.used} 사용 가능</div>
						{:else if gt.used === 0}
							<div class="text-xs text-gray-500">0 사용 중</div>
						{/if}
					</div>
				</button>
			{/each}
		</div>
	</div>
{/if}
