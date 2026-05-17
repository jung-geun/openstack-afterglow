<script lang="ts">
	import { wizard } from '$lib/stores/wizard';
	import { useVmCreate } from '$lib/stores/vmCreateStore.svelte';
	import SelectLibraries from '$lib/components/wizard/SelectLibraries.svelte';
	import SelectTemplate from '$lib/components/wizard/SelectTemplate.svelte';

	const s = useVmCreate();
	const useTemplate = $derived($wizard.templateName !== null);
</script>

<h2 class="text-lg font-semibold text-white mb-1">라이브러리 레이어 <span class="text-gray-500 text-sm font-normal">OverlayFS로 마운트할 사전 빌드 레이어</span></h2>

<div class="flex mb-4 rounded-lg overflow-hidden border border-gray-700">
	<button
		class="flex-1 py-2 text-sm transition-colors {!useTemplate ? 'bg-blue-700 text-white' : 'bg-gray-800 text-gray-400 hover:text-gray-200'}"
		onclick={() => wizard.update(w => ({ ...w, templateName: null, templateVersion: null }))}
	>라이브러리 선택</button>
	<button
		class="flex-1 py-2 text-sm transition-colors {useTemplate ? 'bg-blue-700 text-white' : 'bg-gray-800 text-gray-400 hover:text-gray-200'}"
		onclick={() => wizard.update(w => ({ ...w, libraries: [] }))}
	>템플릿 선택</button>
</div>

{#if useTemplate}
	<SelectTemplate />
{:else}
	<SelectLibraries
		libraries={s.libraries}
		selected={$wizard.libraries}
		hasGpuFlavor={s.hasGpuFlavor}
		ubuntuVersion={s.ubuntuVersion}
		onToggle={s.toggleLibrary}
	/>
{/if}
