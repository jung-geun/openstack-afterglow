<script lang="ts">
	import { wizard } from '$lib/stores/wizard';
	import { useVmCreate } from '$lib/stores/vmCreateStore.svelte';
	import ToggleGroup, { type ToggleOption } from '$lib/components/ui/ToggleGroup.svelte';

	const s = useVmCreate();
	const squashfsEligible = $derived(s.squashfsEligible);
	const squashfsModeOptions: ToggleOption[] = [
		{ value: 'profile', label: '프로필' },
		{ value: 'artifacts', label: '직접 레이어' },
	];

	function selectSquashfsMode(value: string) {
		if (value === 'profile' || value === 'artifacts') s.selectSquashfsMode(value);
	}

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

{#if squashfsEligible}
	<h2 class="mb-1 text-lg font-semibold text-[var(--color-ink-0)]">라이브러리 레이어 <span class="text-sm font-normal text-[var(--color-ink-2)]">VM에 적용할 레이어 선택</span></h2>

	<div class="mb-5 rounded-xl border border-[var(--color-line-2)] bg-[var(--color-surface-raised)] p-4">
		<div class="flex items-start justify-between gap-4 mb-3">
			<div>
				<p class="text-sm font-semibold text-[var(--color-ink-0)]">squashfs 라이브러리 소비</p>
				<p class="mt-1 text-xs leading-5 text-[var(--color-ink-2)]">선택한 Ubuntu 이미지와 같은 Glance base image로 만들어진 공개 프로필/레이어만 사용할 수 있습니다.</p>
			</div>
			{#if $wizard.squashfsMode}
				<button
					class="shrink-0 text-xs text-[var(--color-ink-2)] transition-colors hover:text-[var(--color-ink-0)] focus-visible:outline-none focus-visible:shadow-[var(--focus-ring)]"
					onclick={() => s.clearSquashfsSelection()}
				>선택 해제</button>
			{/if}
		</div>

		<ToggleGroup
			value={$wizard.squashfsMode}
			options={squashfsModeOptions}
			onchange={selectSquashfsMode}
			ariaLabel="squashfs 라이브러리 선택 방식"
			fullWidth
		/>

		{#if $wizard.squashfsMode === 'profile'}
			<div class="space-y-2">
				{#each s.squashfsProfiles as profile (profile.name)}
					{@const baseId = profile.base_image?.base_image_id}
					{@const disabled = Boolean(baseId && baseId !== $wizard.imageId)}
					<button
						class="w-full rounded-lg border px-3 py-3 text-left transition-colors {profile.name === $wizard.layerProfileName ? 'border-[var(--color-accent)] bg-[var(--color-accent)]/10' : 'border-[var(--color-line)] bg-[var(--color-surface-base)]'} {disabled ? 'cursor-not-allowed opacity-50' : 'hover:border-[var(--color-line-2)]'}"
						disabled={disabled}
						onclick={() => s.selectSquashfsProfile(profile.name)}
					>
						<span class="block text-sm font-medium text-[var(--color-ink-0)]">{profile.name}</span>
						<span class="mt-1 block text-xs text-[var(--color-ink-2)]">{profile.layers.length} layers · {profile.base_image?.base_image_name ?? baseId ?? 'base image unknown'}</span>
					</button>
				{/each}
				{#if s.squashfsProfiles.length === 0}
					<p class="rounded-lg border border-[var(--color-line)] bg-[var(--color-surface-base)] p-3 text-sm text-[var(--color-ink-2)]">공개된 squashfs 프로필이 없습니다. 관리자가 프로필을 공개해야 표시됩니다.</p>
				{/if}
			</div>
		{:else if $wizard.squashfsMode === 'artifacts'}
			<div class="space-y-2 max-h-72 overflow-y-auto pr-1">
				{#each s.squashfsArtifacts as artifact (artifact.id)}
					{@const disabled = Boolean(artifact.base_image_id && artifact.base_image_id !== $wizard.imageId)}
					<label class="flex items-start gap-3 rounded-lg border px-3 py-3 {disabled ? 'border-[var(--color-line)] bg-[var(--color-surface-base)] opacity-50' : 'border-[var(--color-line)] bg-[var(--color-surface-base)] hover:border-[var(--color-line-2)]'}">
						<input
							type="checkbox"
							class="mt-1 h-4 w-4 rounded border-[var(--color-line-2)] bg-[var(--color-surface-sunken)] accent-[var(--color-accent)]"
							disabled={disabled}
							checked={$wizard.layerArtifactIds.includes(artifact.id)}
							onchange={() => s.toggleSquashfsArtifact(artifact.id)}
						/>
						<span>
							<span class="block text-sm font-medium text-[var(--color-ink-0)]">{artifact.name}</span>
							<span class="mt-1 block text-xs text-[var(--color-ink-2)]">parent {artifact.parent_id ?? 'root'} · {artifact.base_image_name ?? artifact.base_image_id ?? 'base image unknown'}</span>
						</span>
					</label>
				{/each}
				{#if s.squashfsArtifacts.length === 0}
					<p class="rounded-lg border border-[var(--color-line)] bg-[var(--color-surface-base)] p-3 text-sm text-[var(--color-ink-2)]">공개된 squashfs artifact가 없습니다.</p>
				{/if}
			</div>
		{:else}
			<p class="text-sm text-[var(--color-ink-2)]">프로필 또는 직접 레이어 모드를 선택하지 않으면 일반 VM 생성으로 계속 진행합니다.</p>
		{/if}

		{#if s.squashfsBaseMismatch}
			<p class="mt-3 text-xs text-[var(--color-state-danger)]">선택한 squashfs 레이어의 base image가 부팅 이미지와 일치하지 않습니다.</p>
		{/if}
	</div>
{/if}
