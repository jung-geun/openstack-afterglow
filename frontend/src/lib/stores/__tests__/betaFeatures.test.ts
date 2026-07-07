import { get } from 'svelte/store';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('$app/environment', () => ({ browser: true }));

import { DEFAULT_BETA_FEATURES, betaFeatures, setBetaFeature } from '../betaFeatures';

describe('betaFeatures store', () => {
	beforeEach(() => {
		localStorage.clear();
		betaFeatures.set(DEFAULT_BETA_FEATURES);
	});

	it('persists the squashfs beta toggle in localStorage', () => {
		setBetaFeature('libraryConsume', true);

		expect(get(betaFeatures)).toEqual({ ...DEFAULT_BETA_FEATURES, libraryConsume: true });
		expect(localStorage.getItem('afterglow.beta.libraryConsume')).toBe('true');
		expect(localStorage.getItem('afterglow.beta.haDeploy')).toBe('false');
	});

	it('persists the HA beta toggle without enabling squashfs automatically', () => {
		setBetaFeature('haDeploy', true);

		expect(get(betaFeatures)).toEqual({ ...DEFAULT_BETA_FEATURES, haDeploy: true });
		expect(localStorage.getItem('afterglow.beta.libraryConsume')).toBe('false');
		expect(localStorage.getItem('afterglow.beta.haDeploy')).toBe('true');
	});

	it('persists the Key Manager beta toggle without enabling other validating features', () => {
		setBetaFeature('keyManager', true);

		expect(get(betaFeatures)).toEqual({ ...DEFAULT_BETA_FEATURES, keyManager: true });
		expect(localStorage.getItem('afterglow.beta.keyManager')).toBe('true');
		expect(localStorage.getItem('afterglow.beta.databaseBackups')).toBe('false');
		expect(localStorage.getItem('afterglow.beta.volumeBackups')).toBe('false');
	});

	it('persists the database backup beta toggle without enabling Key Manager', () => {
		setBetaFeature('databaseBackups', true);

		expect(get(betaFeatures)).toEqual({ ...DEFAULT_BETA_FEATURES, databaseBackups: true });
		expect(localStorage.getItem('afterglow.beta.databaseBackups')).toBe('true');
		expect(localStorage.getItem('afterglow.beta.keyManager')).toBe('false');
		expect(localStorage.getItem('afterglow.beta.volumeSnapshots')).toBe('false');
	});
});
