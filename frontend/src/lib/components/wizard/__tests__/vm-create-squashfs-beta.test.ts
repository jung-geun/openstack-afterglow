import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import SelectStrategy from '../SelectStrategy.svelte';
import { DEFAULT_BETA_FEATURES, betaFeatures } from '../../../stores/betaFeatures';
import {
	detectUbuntuBaseImage,
	isSquashfsWizardEligible,
	normalizeSchedulingForBeta,
	shouldUseSquashfsConsume,
	wizardStepSequence,
} from '../../../stores/vmCreateStore.svelte';

const wizardStepSource = readFileSync(resolve(__dirname, '../WizardStep3Library.svelte'), 'utf8');
const strategySource = readFileSync(resolve(__dirname, '../SelectStrategy.svelte'), 'utf8');
const storeSource = readFileSync(resolve(__dirname, '../../../stores/vmCreateStore.svelte.ts'), 'utf8');
const accountSource = readFileSync(resolve(__dirname, '../../../../routes/dashboard/account/+page.svelte'), 'utf8');
const betaStoreSource = readFileSync(resolve(__dirname, '../../../stores/betaFeatures.ts'), 'utf8');

function renderStrategy(props: Partial<{
	scheduling: 'standard' | 'ha';
	strategy: 'prebuilt' | 'dynamic' | null;
	hasLibraries: boolean;
	hasPrebuilt: boolean;
}> = {}) {
	const onSchedulingChange = vi.fn();
	const onStrategyChange = vi.fn();
	const onProtocolChange = vi.fn();
	render(SelectStrategy, {
		props: {
			scheduling: props.scheduling ?? 'standard',
			onSchedulingChange,
			strategy: props.strategy ?? null,
			hasLibraries: props.hasLibraries ?? false,
			hasPrebuilt: props.hasPrebuilt ?? false,
			onStrategyChange,
			mountProtocol: 'NFS',
			onProtocolChange,
		},
	});
	return { onSchedulingChange, onStrategyChange, onProtocolChange };
}

describe('VM create squashfs beta workflow contract', () => {
	beforeEach(() => {
		betaFeatures.set(DEFAULT_BETA_FEATURES);
	});

	it('keeps beta feature preferences on the account page', () => {
		expect(accountSource).toContain('BetaFeaturesSection');
		expect(betaStoreSource).toContain('afterglow.beta.libraryConsume');
		expect(betaStoreSource).toContain('afterglow.beta.haDeploy');
	});

	it('keeps the library step renderable only as squashfs UI when the step is visible', () => {
		expect(wizardStepSource).toContain('squashfs 라이브러리 소비');
		expect(wizardStepSource).not.toContain('SelectLibraries');
		expect(wizardStepSource).not.toContain('SelectTemplate');
		expect(wizardStepSource).not.toContain('계정 설정에서 squashfs 라이브러리 소비 베타');
	});

	it('uses theme tokens for the squashfs selection surface and controls', () => {
		expect(wizardStepSource).toContain('bg-[var(--color-surface-sunken)]');
		expect(wizardStepSource).toContain('border-[var(--color-line-2)]');
		expect(wizardStepSource).toContain('bg-[var(--color-accent)]');
		expect(wizardStepSource).toContain('text-[var(--color-ink-0)]');
		expect(wizardStepSource).not.toContain('bg-blue-950/20');
		expect(wizardStepSource).not.toContain('text-blue-100');
	});

	it('uses ToggleGroup for library mode selection rather than recreating the segmented control', () => {
		expect(wizardStepSource).toContain("import ToggleGroup, { type ToggleOption }");
		expect(wizardStepSource).toContain('value={$wizard.squashfsMode}');
		expect(wizardStepSource).toContain('ariaLabel="squashfs 라이브러리 선택 방식"');
		expect(wizardStepSource).toContain('fullWidth');
		expect(wizardStepSource).not.toContain('aria-pressed');
	});

	it('detects supported Ubuntu images from metadata or image name', () => {
		expect(
			detectUbuntuBaseImage({
				name: 'custom-linux',
				os_distro: 'ubuntu',
				os_version: '22.04-lts',
				properties: null,
			}),
		).toBe('22.04');
		expect(
			detectUbuntuBaseImage({
				name: 'afterglow-ubuntu-24.04',
				os_distro: 'linux',
				os_version: null,
				properties: {},
			}),
		).toBe('24.04');
		expect(detectUbuntuBaseImage({ name: 'rocky-9', properties: {} })).toBeNull();
	});

	it('allows squashfs mode only for beta-enabled Ubuntu image boots in the non-admin wizard', () => {
		expect(
			isSquashfsWizardEligible({
				beta: { libraryConsume: true },
				adminMode: false,
				bootSource: 'image',
				selectedImageUbuntuBase: '22.04',
			}),
		).toBe(true);
		expect(
			isSquashfsWizardEligible({
				beta: { libraryConsume: false },
				adminMode: false,
				bootSource: 'image',
				selectedImageUbuntuBase: '22.04',
			}),
		).toBe(false);
		expect(
			isSquashfsWizardEligible({
				beta: { libraryConsume: true },
				adminMode: false,
				bootSource: 'volume',
				selectedImageUbuntuBase: '22.04',
			}),
		).toBe(false);
		expect(
			isSquashfsWizardEligible({
				beta: { libraryConsume: true },
				adminMode: true,
				bootSource: 'image',
				selectedImageUbuntuBase: '22.04',
			}),
		).toBe(false);
	});

	it('removes hidden beta steps from the wizard sequence instead of showing disabled cards', () => {
		expect(wizardStepSequence({ squashfsEligible: false, haDeploy: false })).toEqual([1, 2, 5, 6]);
		expect(wizardStepSequence({ squashfsEligible: true, haDeploy: false })).toEqual([1, 2, 3, 5, 6]);
		expect(wizardStepSequence({ squashfsEligible: false, haDeploy: true })).toEqual([1, 2, 4, 5, 6]);
		expect(wizardStepSequence({ squashfsEligible: true, haDeploy: true })).toEqual([1, 2, 3, 4, 5, 6]);
	});

	it('uses the public consume router only for eligible, ready squashfs selections', () => {
		expect(
			shouldUseSquashfsConsume({
				beta: { libraryConsume: true },
				adminMode: false,
				bootSource: 'image',
				selectedImageUbuntuBase: '22.04',
				squashfsMode: 'profile',
				layerProfileName: 'ubuntu-base',
				layerArtifactIds: [],
				squashfsBaseMismatch: false,
			}),
		).toBe(true);
		expect(
			shouldUseSquashfsConsume({
				beta: { libraryConsume: true },
				adminMode: false,
				bootSource: 'image',
				selectedImageUbuntuBase: '22.04',
				squashfsMode: 'artifacts',
				layerProfileName: null,
				layerArtifactIds: [1, 2],
				squashfsBaseMismatch: false,
			}),
		).toBe(true);
		expect(
			shouldUseSquashfsConsume({
				beta: { libraryConsume: true },
				adminMode: false,
				bootSource: 'image',
				selectedImageUbuntuBase: '22.04',
				squashfsMode: 'profile',
				layerProfileName: null,
				layerArtifactIds: [],
				squashfsBaseMismatch: false,
			}),
		).toBe(false);
		expect(
			shouldUseSquashfsConsume({
				beta: { libraryConsume: true },
				adminMode: false,
				bootSource: 'image',
				selectedImageUbuntuBase: '22.04',
				squashfsMode: 'artifacts',
				layerProfileName: null,
				layerArtifactIds: [1],
				squashfsBaseMismatch: true,
			}),
		).toBe(false);
		expect(
			shouldUseSquashfsConsume({
				beta: { libraryConsume: false },
				adminMode: false,
				bootSource: 'image',
				selectedImageUbuntuBase: '22.04',
				squashfsMode: 'profile',
				layerProfileName: 'ubuntu-base',
				layerArtifactIds: [],
				squashfsBaseMismatch: false,
			}),
		).toBe(false);
	});

	it('coerces stale HA scheduling off when the HA beta is disabled', () => {
		expect(normalizeSchedulingForBeta({ haDeploy: false }, 'ha')).toBe('standard');
		expect(normalizeSchedulingForBeta({ haDeploy: true }, 'ha')).toBe('ha');
		expect(storeSource).toContain('/api/v1/libraries/squashfs/consume');
		expect(storeSource).toContain('normalizeSchedulingForBeta(betaState, w.scheduling)');
		expect(storeSource).toContain('normalizeRequestedInstanceName(w.instanceName)');
	});

	it('hides the HA option in the strategy step unless the beta flag is enabled', async () => {
		const { onSchedulingChange } = renderStrategy({ scheduling: 'ha' });

		await waitFor(() => {
			expect(onSchedulingChange).toHaveBeenCalledWith('standard');
		});
		expect(screen.queryByText('HA 배포')).toBeNull();
		expect(strategySource).toContain('$betaFeatures.haDeploy');
	});

	it('shows the HA option when the HA beta is enabled', () => {
		betaFeatures.set({ ...DEFAULT_BETA_FEATURES, haDeploy: true });
		renderStrategy();
		expect(screen.getByText('HA 배포')).toBeTruthy();
	});
});
