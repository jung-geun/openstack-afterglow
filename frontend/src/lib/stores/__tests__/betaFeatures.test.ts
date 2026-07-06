import { get } from 'svelte/store';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('$app/environment', () => ({ browser: true }));

import { betaFeatures, setBetaFeature } from '../betaFeatures';

describe('betaFeatures store', () => {
	beforeEach(() => {
		localStorage.clear();
		betaFeatures.set({ libraryConsume: false, haDeploy: false });
	});

	it('persists the squashfs beta toggle in localStorage', () => {
		setBetaFeature('libraryConsume', true);

		expect(get(betaFeatures)).toEqual({ libraryConsume: true, haDeploy: false });
		expect(localStorage.getItem('afterglow.beta.libraryConsume')).toBe('true');
		expect(localStorage.getItem('afterglow.beta.haDeploy')).toBe('false');
	});

	it('persists the HA beta toggle without enabling squashfs automatically', () => {
		setBetaFeature('haDeploy', true);

		expect(get(betaFeatures)).toEqual({ libraryConsume: false, haDeploy: true });
		expect(localStorage.getItem('afterglow.beta.libraryConsume')).toBe('false');
		expect(localStorage.getItem('afterglow.beta.haDeploy')).toBe('true');
	});
});
