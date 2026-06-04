<script lang="ts">
	import SlidePanel from '$lib/components/SlidePanel.svelte';
	import FlavorAccessTab from './FlavorAccessTab.svelte';
	import FlavorExtraSpecsTab from './FlavorExtraSpecsTab.svelte';

	interface Flavor {
		id: string;
		name: string;
		vcpus: number;
		ram: number;
		disk: number;
		is_public: boolean;
		description: string | null;
		extra_specs: Record<string, string>;
		is_gpu: boolean;
		gpu_count: number;
	}

	let {
		flavor,
		onClose,
		onChanged,
	}: {
		flavor: Flavor | null;
		onClose: () => void;
		onChanged: () => void;
	} = $props();

	let activeTab = $state<'access' | 'properties'>('access');

	function formatRam(mb: number): string {
		if (mb >= 1024) return `${(mb / 1024).toFixed(mb % 1024 === 0 ? 0 : 1)} GB`;
		return `${mb} MB`;
	}
</script>

{#if flavor}
	<SlidePanel {onClose} width="w-full md:w-[640px]">
		<div class="p-6">
			<div class="flex items-center justify-between mb-4">
				<h2 class="text-lg font-semibold text-white">Flavor 관리</h2>
				<button onclick={onClose} class="text-gray-400 hover:text-white text-xl">&times;</button>
			</div>
			<div class="mb-4">
				<div class="text-sm text-gray-400">Flavor</div>
				<div class="text-white font-medium">{flavor.name}</div>
				<div class="text-xs text-gray-500">{flavor.vcpus} VCPU / {formatRam(flavor.ram)} / {flavor.disk} GB</div>
				<button
					onclick={() => navigator.clipboard.writeText(flavor!.id)}
					class="mt-1 text-xs text-gray-500 font-mono hover:text-gray-300 transition-colors cursor-pointer select-all"
					title="클릭하여 ID 복사"
				>{flavor.id}</button>
			</div>

			<div class="flex border-b border-gray-800 mb-4">
				<button
					onclick={() => (activeTab = 'access')}
					class="px-4 py-2 text-sm {activeTab === 'access' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-gray-400 hover:text-gray-200'}"
				>접근 관리</button>
				<button
					onclick={() => (activeTab = 'properties')}
					class="px-4 py-2 text-sm {activeTab === 'properties' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-gray-400 hover:text-gray-200'}"
				>속성 (extra_specs)</button>
			</div>

			{#if activeTab === 'access'}
				<FlavorAccessTab {flavor} />
			{:else}
				<FlavorExtraSpecsTab {flavor} {onChanged} />
			{/if}
		</div>
	</SlidePanel>
{/if}
