<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { auth } from '$lib/stores/auth';
	import { wizard, resetWizard } from '$lib/stores/wizard';
	import { api, ApiError } from '$lib/api/client';
	import SelectImage from '$lib/components/wizard/SelectImage.svelte';
	import SelectFlavor from '$lib/components/wizard/SelectFlavor.svelte';
	import SelectLibraries from '$lib/components/wizard/SelectLibraries.svelte';
	import SelectStrategy from '$lib/components/wizard/SelectStrategy.svelte';

	const TOTAL_STEPS = 5;

	let images = $state<any[]>([]);
	let flavors = $state<any[]>([]);
	let libraries = $state<any[]>([]);
	let loadError = $state('');
	let deploying = $state(false);
	let deployError = $state('');

	onMount(async () => {
		resetWizard();
		const token = $auth.token ?? undefined;
		const projectId = $auth.projectId ?? undefined;
		try {
			[images, flavors, libraries] = await Promise.all([
				api.get<any[]>('/api/images', token, projectId),
				api.get<any[]>('/api/flavors', token, projectId),
				api.get<any[]>('/api/libraries', token, projectId),
			]);
		} catch (e) {
			loadError = e instanceof ApiError ? `데이터 로드 실패 (${e.status})` : '서버 오류';
		}
	});

	function nextStep() {
		if ($wizard.step < TOTAL_STEPS) wizard.update(w => ({ ...w, step: w.step + 1 }));
	}
	function prevStep() {
		if ($wizard.step > 1) wizard.update(w => ({ ...w, step: w.step - 1 }));
	}

	function selectImage(id: string, name: string) {
		wizard.update(w => ({ ...w, imageId: id, imageName: name }));
	}
	function selectFlavor(id: string, name: string) {
		wizard.update(w => ({ ...w, flavorId: id, flavorName: name }));
	}

	function toggleLibrary(id: string, deps: string[]) {
		wizard.update(w => {
			const libs = new Set(w.libraries);
			if (libs.has(id)) {
				libs.delete(id);
			} else {
				libs.add(id);
				deps.forEach(d => libs.add(d));
			}
			return { ...w, libraries: Array.from(libs) };
		});
	}

	function selectStrategy(s: 'prebuilt' | 'dynamic') {
		wizard.update(w => ({ ...w, strategy: s }));
	}

	let hasGpuFlavor = $derived(
		flavors.find(f => f.id === $wizard.flavorId)
			? Object.keys(flavors.find(f => f.id === $wizard.flavorId)?.extra_specs ?? {}).some(
					k => k.toLowerCase().includes('gpu')
				)
			: false
	);

	let hasPrebuilt = $derived(
		libraries.some(l => $wizard.libraries.includes(l.id) && l.available_prebuilt)
	);

	let canNext = $derived((() => {
		switch ($wizard.step) {
			case 1: return !!$wizard.imageId;
			case 2: return !!$wizard.flavorId;
			case 3: return true;
			case 4: return true;
			case 5: return !!$wizard.instanceName.trim();
			default: return false;
		}
	})());

	async function deploy() {
		deployError = '';
		deploying = true;
		try {
			await api.post('/api/instances', {
				name: $wizard.instanceName,
				image_id: $wizard.imageId,
				flavor_id: $wizard.flavorId,
				libraries: $wizard.libraries,
				strategy: $wizard.strategy,
				network_id: $wizard.networkId,
				key_name: $wizard.keyName,
			}, $auth.token ?? undefined, $auth.projectId ?? undefined);
			resetWizard();
			goto('/dashboard');
		} catch (e) {
			deployError = e instanceof ApiError ? `배포 실패: ${e.message}` : '서버 오류';
		} finally {
			deploying = false;
		}
	}

	const stepLabels = ['이미지', '플레이버', '라이브러리', '전략', '배포'];
</script>

<div class="p-8 max-w-3xl mx-auto">
	<h1 class="text-2xl font-bold text-white mb-6">VM 생성</h1>

	{#if loadError}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-6">
			{loadError}
		</div>
	{/if}

	<!-- 단계 표시 -->
	<div class="flex items-center gap-2 mb-8">
		{#each stepLabels as label, i}
			{@const step = i + 1}
			<div class="flex items-center gap-2">
				<div class="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-all {$wizard.step === step
					? 'bg-blue-600 text-white'
					: $wizard.step > step
					? 'bg-green-700 text-white'
					: 'bg-gray-800 text-gray-500'}">
					{$wizard.step > step ? '✓' : step}
				</div>
				<span class="text-xs {$wizard.step === step ? 'text-white' : 'text-gray-600'}">{label}</span>
			</div>
			{#if i < stepLabels.length - 1}
				<div class="flex-1 h-px bg-gray-800"></div>
			{/if}
		{/each}
	</div>

	<!-- 단계별 내용 -->
	<div class="mb-8">
		{#if $wizard.step === 1}
			<h2 class="text-lg font-semibold text-white mb-4">OS 이미지 선택</h2>
			<SelectImage {images} selectedId={$wizard.imageId} onSelect={selectImage} />

		{:else if $wizard.step === 2}
			<h2 class="text-lg font-semibold text-white mb-4">플레이버 선택</h2>
			<SelectFlavor {flavors} selectedId={$wizard.flavorId} onSelect={selectFlavor} />

		{:else if $wizard.step === 3}
			<h2 class="text-lg font-semibold text-white mb-4">라이브러리 선택</h2>
			<SelectLibraries
				{libraries}
				selected={$wizard.libraries}
				{hasGpuFlavor}
				onToggle={toggleLibrary}
			/>

		{:else if $wizard.step === 4}
			<h2 class="text-lg font-semibold text-white mb-4">마운트 전략 선택</h2>
			<SelectStrategy
				selected={$wizard.strategy}
				{hasPrebuilt}
				onSelect={selectStrategy}
			/>

		{:else if $wizard.step === 5}
			<h2 class="text-lg font-semibold text-white mb-4">최종 확인 및 배포</h2>

			<div class="bg-gray-900 rounded-xl border border-gray-700 p-6 space-y-3 mb-6 text-sm">
				<div class="flex justify-between">
					<span class="text-gray-400">이미지</span>
					<span class="text-white">{$wizard.imageName ?? '-'}</span>
				</div>
				<div class="flex justify-between">
					<span class="text-gray-400">플레이버</span>
					<span class="text-white">{$wizard.flavorName ?? '-'}</span>
				</div>
				<div class="flex justify-between">
					<span class="text-gray-400">라이브러리</span>
					<span class="text-white">
						{$wizard.libraries.length > 0 ? $wizard.libraries.join(', ') : '없음'}
					</span>
				</div>
				<div class="flex justify-between">
					<span class="text-gray-400">전략</span>
					<span class="text-white">
						{$wizard.strategy === 'prebuilt' ? 'A: 사전 빌드 공유 Share' : 'B: 동적 생성'}
					</span>
				</div>
			</div>

			<div class="mb-4">
				<label for="instance-name" class="block text-gray-400 text-xs mb-1.5 uppercase tracking-wide">인스턴스 이름</label>
				<input
					id="instance-name"
					bind:value={$wizard.instanceName}
					type="text"
					placeholder="my-vm"
					class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
				/>
			</div>

			{#if deployError}
				<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-4">
					{deployError}
				</div>
			{/if}
		{/if}
	</div>

	<!-- 네비게이션 버튼 -->
	<div class="flex justify-between">
		<button
			onclick={prevStep}
			disabled={$wizard.step === 1}
			class="px-4 py-2 text-sm text-gray-400 hover:text-white disabled:opacity-30 transition-colors"
		>
			← 이전
		</button>

		{#if $wizard.step < TOTAL_STEPS}
			<button
				onclick={nextStep}
				disabled={!canNext}
				class="px-6 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors"
			>
				다음 →
			</button>
		{:else}
			<button
				onclick={deploy}
				disabled={deploying || !canNext}
				class="px-6 py-2 bg-green-600 hover:bg-green-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors"
			>
				{deploying ? '배포 중...' : '배포 시작'}
			</button>
		{/if}
	</div>
</div>
