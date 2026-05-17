<script lang="ts">
	import { createFileStorageWizardStore, provideFsWizard } from '$lib/stores/fileStorageWizardStore.svelte';
	import FileStorageWizardStep1 from './FileStorageWizardStep1.svelte';
	import FileStorageWizardStep2 from './FileStorageWizardStep2.svelte';
	import FileStorageWizardStep3 from './FileStorageWizardStep3.svelte';

	let {
		open = $bindable(false),
		onCreated,
	}: {
		open: boolean;
		onCreated: () => void;
	} = $props();

	const s = createFileStorageWizardStore({
		open: () => open,
		setOpen: (v) => { open = v; },
		onCreated: () => onCreated(),
	});
	provideFsWizard(s);
</script>

{#if open}
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
		onclick={s.closeWizard}
		role="dialog" aria-modal="true" tabindex="-1"
		onkeydown={(e) => e.key === 'Escape' && s.closeWizard()}
	>
		<div
			class="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-xl mx-4 shadow-2xl max-h-[90vh] overflow-y-auto"
			onclick={(e) => e.stopPropagation()}
			role="none"
			onkeydown={(e) => e.stopPropagation()}
		>
			<!-- 스텝 인디케이터 -->
			<div class="flex items-center gap-0 px-6 pt-6 pb-4 border-b border-gray-800">
				{#each [
					{ step: 1, label: '기본 정보' },
					{ step: 2, label: '네트워크' },
					{ step: 3, label: '접근 설정' },
				] as item}
					<div class="flex items-center {item.step < 3 ? 'flex-1' : ''}">
						<div class="flex flex-col items-center">
							<div class="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold border-2 transition-colors
								{s.step === item.step ? 'border-blue-500 bg-blue-900/40 text-blue-400' :
								 s.step > item.step ? 'border-green-600 bg-green-900/30 text-green-400' :
								 'border-gray-700 bg-gray-800 text-gray-500'}">
								{s.step > item.step ? '✓' : item.step}
							</div>
							<span class="text-xs mt-1 {s.step === item.step ? 'text-blue-400' : s.step > item.step ? 'text-green-400' : 'text-gray-600'}">{item.label}</span>
						</div>
						{#if item.step < 3}
							<div class="flex-1 h-px mx-3 mt-[-14px] {s.step > item.step ? 'bg-green-700' : 'bg-gray-700'}"></div>
						{/if}
					</div>
				{/each}
			</div>

			<div class="p-6">
				{#if s.step === 1}
					<FileStorageWizardStep1 />
				{:else if s.step === 2}
					<FileStorageWizardStep2 />
				{:else if s.step === 3 && s.createdFs}
					<FileStorageWizardStep3 />
				{/if}
			</div>
		</div>
	</div>
{/if}
