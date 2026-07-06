<script lang="ts">
	import { wizard } from '$lib/stores/wizard';
	import { betaFeatures } from '$lib/stores/betaFeatures';
	import { useVmCreate } from '$lib/stores/vmCreateStore.svelte';

	const s = useVmCreate();
	const squashfsEligible = $derived(s.squashfsEligible);

	$effect(() => {
		const hasLegacySelection =
			$wizard.libraries.length > 0 ||
			$wizard.templateName !== null ||
			$wizard.templateVersion !== null ||
			$wizard.strategy !== null;
		const hasInvalidSquashfsSelection = !squashfsEligible && $wizard.squashfsMode;
		if (!hasLegacySelection && !hasInvalidSquashfsSelection) return;
		wizard.update(w => ({
			...w,
			libraries: [],
			templateName: null,
			templateVersion: null,
			strategy: null,
			...(squashfsEligible ? {} : { squashfsMode: null, layerProfileName: null, layerArtifactIds: [] }),
		}));
	});
</script>

<h2 class="text-lg font-semibold text-white mb-1">라이브러리 레이어 <span class="text-gray-500 text-sm font-normal">VM에 적용할 레이어 선택</span></h2>

{#if squashfsEligible}
	<div class="mb-5 rounded-xl border border-blue-900/60 bg-blue-950/20 p-4">
		<div class="flex items-start justify-between gap-4 mb-3">
			<div>
				<p class="text-sm font-semibold text-blue-100">squashfs 라이브러리 소비</p>
				<p class="text-xs text-blue-200/70 mt-1">선택한 Ubuntu 이미지와 같은 Glance base image로 만들어진 공개 프로필/레이어만 사용할 수 있습니다.</p>
			</div>
			<button class="text-xs text-gray-400 hover:text-white" onclick={() => s.clearSquashfsSelection()}>선택 해제</button>
		</div>

		<div class="grid grid-cols-2 gap-2 mb-4">
			<button
				class="rounded-lg px-3 py-2 text-sm border transition-colors {$wizard.squashfsMode === 'profile' ? 'border-blue-500 bg-blue-600/20 text-white' : 'border-gray-700 bg-gray-900 text-gray-300 hover:text-white'}"
				onclick={() => s.selectSquashfsMode('profile')}
			>프로필</button>
			<button
				class="rounded-lg px-3 py-2 text-sm border transition-colors {$wizard.squashfsMode === 'artifacts' ? 'border-blue-500 bg-blue-600/20 text-white' : 'border-gray-700 bg-gray-900 text-gray-300 hover:text-white'}"
				onclick={() => s.selectSquashfsMode('artifacts')}
			>직접 레이어</button>
		</div>

		{#if $wizard.squashfsMode === 'profile'}
			<div class="space-y-2">
				{#each s.squashfsProfiles as profile (profile.name)}
					{@const baseId = profile.base_image?.base_image_id}
					{@const disabled = Boolean(baseId && baseId !== $wizard.imageId)}
					<button
						class="w-full text-left rounded-lg border px-3 py-3 transition-colors {profile.name === $wizard.layerProfileName ? 'border-blue-500 bg-blue-600/20' : 'border-gray-800 bg-gray-950/50'} {disabled ? 'opacity-50 cursor-not-allowed' : 'hover:border-gray-600'}"
						disabled={disabled}
						onclick={() => s.selectSquashfsProfile(profile.name)}
					>
						<span class="block text-sm font-medium text-white">{profile.name}</span>
						<span class="block text-xs text-gray-400 mt-1">{profile.layers.length} layers · {profile.base_image?.base_image_name ?? baseId ?? 'base image unknown'}</span>
					</button>
				{/each}
				{#if s.squashfsProfiles.length === 0}
					<p class="text-sm text-gray-400 rounded-lg border border-gray-800 bg-gray-950/50 p-3">공개된 squashfs 프로필이 없습니다. 관리자가 프로필을 공개해야 표시됩니다.</p>
				{/if}
			</div>
		{:else if $wizard.squashfsMode === 'artifacts'}
			<div class="space-y-2 max-h-72 overflow-y-auto pr-1">
				{#each s.squashfsArtifacts as artifact (artifact.id)}
					{@const disabled = Boolean(artifact.base_image_id && artifact.base_image_id !== $wizard.imageId)}
					<label class="flex items-start gap-3 rounded-lg border px-3 py-3 {disabled ? 'border-gray-900 bg-gray-950/30 opacity-50' : 'border-gray-800 bg-gray-950/50 hover:border-gray-600'}">
						<input
							type="checkbox"
							class="mt-1 h-4 w-4 rounded border-gray-600 bg-gray-800 text-blue-600"
							disabled={disabled}
							checked={$wizard.layerArtifactIds.includes(artifact.id)}
							onchange={() => s.toggleSquashfsArtifact(artifact.id)}
						/>
						<span>
							<span class="block text-sm font-medium text-white">{artifact.name}</span>
							<span class="block text-xs text-gray-400 mt-1">parent {artifact.parent_id ?? 'root'} · {artifact.base_image_name ?? artifact.base_image_id ?? 'base image unknown'}</span>
						</span>
					</label>
				{/each}
				{#if s.squashfsArtifacts.length === 0}
					<p class="text-sm text-gray-400 rounded-lg border border-gray-800 bg-gray-950/50 p-3">공개된 squashfs artifact가 없습니다.</p>
				{/if}
			</div>
		{:else}
			<p class="text-sm text-gray-400">프로필 또는 직접 레이어 모드를 선택하지 않으면 일반 VM 생성으로 계속 진행합니다.</p>
		{/if}

		{#if s.squashfsBaseMismatch}
			<p class="mt-3 text-xs text-red-300">선택한 squashfs 레이어의 base image가 부팅 이미지와 일치하지 않습니다.</p>
		{/if}
	</div>
{:else}
	<div class="mb-5 rounded-xl border border-gray-800 bg-gray-950/40 p-4 text-sm text-gray-400">
		{#if !$betaFeatures.libraryConsume}
			계정 설정에서 squashfs 라이브러리 소비 베타를 켜면 이 단계에서 공개 프로필/레이어를 선택할 수 있습니다.
		{:else if $wizard.bootSource !== 'image'}
			squashfs 소비는 이미지 부팅 VM에서만 지원됩니다. 볼륨 부팅에서는 일반 VM 생성으로 진행합니다.
		{:else}
			선택한 부팅 이미지가 지원되는 Ubuntu 18.04/20.04/22.04/24.04 이미지로 식별되지 않았습니다.
		{/if}
	</div>
{/if}
