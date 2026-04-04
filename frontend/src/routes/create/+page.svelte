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
	import ProgressBar from '$lib/components/ProgressBar.svelte';
	import LoadingSpinner from '$lib/components/LoadingSpinner.svelte';

	const TOTAL_STEPS = 6;

	interface ProgressMessage {
		step: string;
		progress: number;
		message: string;
		instance_id?: string;
		error?: string;
	}

	interface NetworkInfo {
		id: string;
		name: string;
		status: string;
		is_external: boolean;
		is_shared: boolean;
	}

	interface KeypairInfo {
		name: string;
		fingerprint: string;
		type: string;
	}

	const PROGRESS_STEPS = [
		{ id: 'manila_preparing', label: 'Manila Shares', description: '공유 스토리지 준비' },
		{ id: 'boot_volume_creating', label: '부트 볼륨', description: 'OS 이미지 볼륨 생성' },
		{ id: 'upper_volume_creating', label: 'Upper 볼륨', description: 'OverlayFS upperdir 생성' },
		{ id: 'userdata_generating', label: 'cloud-init', description: '초기화 스크립트 생성' },
		{ id: 'server_creating', label: 'VM 생성', description: 'Nova 인스턴스 생성' },
		{ id: 'attaching_volume', label: '볼륨 연결', description: '추가 볼륨 연결' },
		{ id: 'floating_ip_creating', label: 'Floating IP', description: 'Floating IP 할당' },
		{ id: 'completed', label: '완료', description: '배포 완료' },
		{ id: 'failed', label: '실패', description: '배포 실패' },
	];

	let images = $state<any[]>([]);
	let flavors = $state<any[]>([]);
	let libraries = $state<any[]>([]);
	let networks = $state<NetworkInfo[]>([]);
	let keypairs = $state<KeypairInfo[]>([]);
	let loadError = $state('');
	let deploying = $state(false);
	let deployError = $state('');
	let currentStep = $state('manila_preparing');
	let progress = $state(0);
	let progressMessage = $state('');

	onMount(async () => {
		resetWizard();
		const token = $auth.token ?? undefined;
		const projectId = $auth.projectId ?? undefined;
		try {
			[images, flavors, libraries, networks, keypairs] = await Promise.all([
				api.get<any[]>('/api/images', token, projectId),
				api.get<any[]>('/api/flavors', token, projectId),
				api.get<any[]>('/api/libraries', token, projectId),
				api.get<NetworkInfo[]>('/api/networks', token, projectId),
				api.get<KeypairInfo[]>('/api/keypairs', token, projectId),
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

	function selectNetwork(id: string | null) {
		const net = networks.find(n => n.id === id) ?? null;
		wizard.update(w => ({ ...w, networkId: id, networkName: net?.name ?? null }));
	}

	let selectedNetwork = $derived(
		$wizard.networkId ? networks.find(n => n.id === $wizard.networkId) ?? null : null
	);

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
			case 5: return true;
			case 6: return !!$wizard.instanceName.trim();
			default: return false;
		}
	})());

	async function deploy() {
		deployError = '';
		deploying = true;
		currentStep = 'manila_preparing';
		progress = 0;
		progressMessage = '배포 시작...';

		const baseUrl = typeof window !== 'undefined'
			? (import.meta.env.PUBLIC_API_BASE || `${window.location.protocol}//${window.location.hostname}:8000`)
			: 'http://backend:8000';

		const headers: Record<string, string> = {
			'Content-Type': 'application/json',
			'Accept': 'text/event-stream'
		};
		if ($auth.token) headers['X-Auth-Token'] = $auth.token;
		if ($auth.projectId) headers['X-Project-Id'] = $auth.projectId;

		try {
			const response = await fetch(`${baseUrl}/api/instances/async`, {
				method: 'POST',
				headers,
				body: JSON.stringify({
					name: $wizard.instanceName,
					image_id: $wizard.imageId,
					flavor_id: $wizard.flavorId,
					libraries: $wizard.libraries,
					strategy: $wizard.strategy,
					network_id: $wizard.networkId,
					key_name: $wizard.keyName,
					boot_volume_size_gb: $wizard.bootVolumeSizeGb,
				})
			});

			if (!response.ok) {
				const text = await response.text();
				throw new ApiError(response.status, text || response.statusText);
			}

			const reader = response.body?.getReader();
			if (!reader) throw new Error('No response body');

			const decoder = new TextDecoder();
			let buffer = '';

			while (true) {
				const { done, value } = await reader.read();
				if (done) break;

				buffer += decoder.decode(value, { stream: true });
				const lines = buffer.split('\n');
				buffer = lines.pop() || '';

				for (const line of lines) {
					if (line.startsWith('data: ')) {
						try {
							const data = JSON.parse(line.slice(6)) as ProgressMessage;
							currentStep = data.step;
							progress = data.progress;
							progressMessage = data.message;

							if (data.step === 'completed') {
								setTimeout(() => {
									resetWizard();
									goto('/dashboard');
								}, 1000);
								return;
							}

							if (data.step === 'failed') {
								deployError = data.error || data.message;
								deploying = false;
								return;
							}
						} catch {
							// JSON 파싱 실패 시 무시
						}
					}
				}
			}
		} catch (e) {
			deployError = e instanceof ApiError ? `배포 실패: ${e.message}` : '서버 오류';
			deploying = false;
		}
	}

	const stepLabels = ['이미지', '플레이버', '라이브러리', '전략', '설정', '배포'];
</script>

<div class="p-8 max-w-3xl mx-auto">
	<h1 class="text-2xl font-bold text-white mb-6">VM 생성</h1>

	{#if loadError}
		<div class="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm mb-6">
			{loadError}
		</div>
	{/if}

	<!-- 배포 진행 중 Progress Bar -->
	{#if deploying}
		<div class="bg-gray-900 rounded-xl border border-gray-700 p-6 mb-6">
			<h2 class="text-lg font-semibold text-white mb-4">VM 배포 진행 중</h2>
			<ProgressBar
				steps={PROGRESS_STEPS}
				currentStep={currentStep}
				progress={progress}
				error={deployError}
			/>
			<p class="text-gray-400 text-sm mt-4">{progressMessage}</p>
		</div>

		<div class="flex justify-end">
			<button
				disabled
				class="px-6 py-2 bg-gray-700 text-gray-500 text-sm font-medium rounded-lg cursor-not-allowed"
			>
				<LoadingSpinner size="sm" color="gray">
					배포 중...
				</LoadingSpinner>
			</button>
		</div>
	{:else}
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
				<h2 class="text-lg font-semibold text-white mb-4">인스턴스 설정</h2>

				<!-- 키페어 선택 -->
				<div class="mb-6">
					<label class="block text-gray-400 text-xs mb-1.5 uppercase tracking-wide">키페어 (SSH 접속용)</label>
					<select
						value={$wizard.keyName}
						onchange={e => wizard.update(w => ({ ...w, keyName: (e.target as HTMLSelectElement).value || null }))}
						class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
					>
						<option value="">선택 안 함</option>
						{#each keypairs as kp}
							<option value={kp.name}>{kp.name} · {kp.type} · {kp.fingerprint.slice(0, 20)}…</option>
						{/each}
					</select>
					{#if keypairs.length === 0}
						<p class="text-xs text-amber-400 mt-1">등록된 키페어가 없습니다. SSH 접속을 위해 키페어를 먼저 등록하세요.</p>
					{/if}
				</div>

				<!-- 루트 볼륨 크기 -->
				<div class="mb-6">
					<label class="block text-gray-400 text-xs mb-1.5 uppercase tracking-wide">루트 볼륨 크기 (GB)</label>
					<input
						type="number"
						bind:value={$wizard.bootVolumeSizeGb}
						min="10"
						max="500"
						class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
					/>
					<p class="text-xs text-gray-500 mt-1">OS 루트 볼륨 크기. 최소 10GB, 기본 20GB.</p>
				</div>

				<!-- 네트워크 선택 -->
				<div class="mb-6">
					<label class="block text-gray-400 text-xs mb-1.5 uppercase tracking-wide">네트워크</label>
					<select
						value={$wizard.networkId ?? ''}
						onchange={e => selectNetwork((e.target as HTMLSelectElement).value || null)}
						class="w-full bg-gray-800 border border-gray-600 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500 transition-colors"
					>
						<option value="">기본 네트워크</option>
						{#each networks as net}
							<option value={net.id}>
								{net.name}{net.is_external ? ' (외부)' : ''}{net.is_shared ? ' (공유)' : ''}
							</option>
						{/each}
					</select>
					{#if selectedNetwork && !selectedNetwork.is_external}
						<p class="text-xs text-amber-400 mt-1">
							내부 네트워크 선택 시 외부 접속을 위해 Floating IP가 자동으로 할당됩니다.
						</p>
					{/if}
				</div>

			{:else if $wizard.step === 6}
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
					<div class="flex justify-between">
						<span class="text-gray-400">키페어</span>
						<span class="text-white">{$wizard.keyName ?? '없음'}</span>
					</div>
					<div class="flex justify-between">
						<span class="text-gray-400">루트 볼륨</span>
						<span class="text-white">{$wizard.bootVolumeSizeGb} GB</span>
					</div>
					<div class="flex justify-between">
						<span class="text-gray-400">네트워크</span>
						<span class="text-white">
							{$wizard.networkName ?? '기본'}
							{#if selectedNetwork && !selectedNetwork.is_external}
								<span class="text-amber-400 text-xs ml-1">(Floating IP 자동 할당)</span>
							{/if}
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
					disabled={!canNext}
					class="px-6 py-2 bg-green-600 hover:bg-green-500 disabled:bg-gray-700 disabled:text-gray-500 text-white text-sm font-medium rounded-lg transition-colors"
				>
					배포 시작
				</button>
			{/if}
		</div>
	{/if}
</div>
