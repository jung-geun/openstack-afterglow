<script lang="ts">
	import { onMount } from 'svelte';
	import { wizard, closeWizard } from '$lib/stores/wizard';
	import { createVmCreateStore, provideVmCreate, TOTAL_STEPS, STEP_LABELS } from '$lib/stores/vmCreateStore.svelte';
	import SelectFlavor from '$lib/components/wizard/SelectFlavor.svelte';
	import SelectStrategy from '$lib/components/wizard/SelectStrategy.svelte';
	import WizardStepper from '$lib/components/wizard/WizardStepper.svelte';
	import WizardHeader from '$lib/components/wizard/WizardHeader.svelte';
	import WizardFooter from '$lib/components/wizard/WizardFooter.svelte';
	import LoadingSpinner from '$lib/components/LoadingSpinner.svelte';
	import SlidePanel from '$lib/components/SlidePanel.svelte';
	import AdminProjectSelector from '$lib/components/wizard/AdminProjectSelector.svelte';
	import VmDeployProgress from '$lib/components/wizard/VmDeployProgress.svelte';
	import WizardStep1Boot from '$lib/components/wizard/WizardStep1Boot.svelte';
	import WizardStep3Library from '$lib/components/wizard/WizardStep3Library.svelte';
	import WizardStep5Config from '$lib/components/wizard/WizardStep5Config.svelte';
	import WizardStep6Review from '$lib/components/wizard/WizardStep6Review.svelte';

	interface Props {
		adminMode?: boolean;
	}
	let { adminMode = false }: Props = $props();

	const s = createVmCreateStore({ adminMode: () => adminMode });
	provideVmCreate(s);

	onMount(() => s.init());
</script>

<SlidePanel onClose={closeWizard} width="w-full md:w-[75vw] max-w-4xl">
	<div class="p-4 md:p-8">
		{#if s.needsProjectSelect}
			<AdminProjectSelector />
		{:else if s.loading}
			<div class="flex items-center justify-center py-16">
				<LoadingSpinner size="lg" color="blue">데이터 로드 중...</LoadingSpinner>
			</div>
		{:else if s.deploying}
			<VmDeployProgress />
		{:else}
			<WizardHeader
				step={$wizard.step}
				totalSteps={TOTAL_STEPS}
				stepName={STEP_LABELS[$wizard.step - 1]}
				{adminMode}
				adminProjectName={s.adminSelectedProjectName}
				onReset={s.handleReset}
				onClose={closeWizard}
			/>

			{#if s.loadError}
				<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-6">
					{s.loadError}
				</div>
			{/if}

			<WizardStepper cur={$wizard.step} totalSteps={TOTAL_STEPS} stepLabels={STEP_LABELS} goTo={s.goTo} />

			<div class="mb-8">
				{#if $wizard.step === 1}
					<WizardStep1Boot />
				{:else if $wizard.step === 2}
					<h2 class="text-lg font-semibold text-white mb-1">플레이버 선택 <span class="text-gray-500 text-sm font-normal">VM의 vCPU / 메모리 / 디스크 스펙</span></h2>
					<SelectFlavor flavors={s.flavors} selectedId={$wizard.flavorId} onSelect={s.selectFlavor} quota={s.flavorQuota} />
				{:else if $wizard.step === 3}
					<WizardStep3Library />
				{:else if $wizard.step === 4}
					<h2 class="text-lg font-semibold text-white mb-4">배포 전략 <span class="text-gray-500 text-sm font-normal">스케줄링 / 레이어 마운트</span></h2>
					<SelectStrategy
						scheduling={$wizard.scheduling}
						onSchedulingChange={s.selectScheduling}
						strategy={$wizard.strategy}
						hasLibraries={$wizard.libraries.length > 0}
						hasPrebuilt={s.hasPrebuilt}
						onStrategyChange={s.selectStrategy}
						mountProtocol={$wizard.mountProtocol}
						onProtocolChange={s.selectMountProtocol}
					/>
				{:else if $wizard.step === 5}
					<WizardStep5Config />
				{:else if $wizard.step === 6}
					<WizardStep6Review />
				{/if}
			</div>

			<WizardFooter
				imageDisplay={$wizard.imageName ?? ($wizard.bootSource === 'volume' ? ($wizard.bootVolumeName ?? null) : null)}
				flavorDisplay={$wizard.flavorName}
				libCount={$wizard.libraries.length}
				step={$wizard.step}
				totalSteps={TOTAL_STEPS}
				canPrev={$wizard.step > 1}
				canNext={s.canNext}
				onCancel={closeWizard}
				onPrev={s.prevStep}
				onNext={s.nextStep}
				onDeploy={s.deploy}
			/>
		{/if}
	</div>
</SlidePanel>
