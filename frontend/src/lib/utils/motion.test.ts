import { afterEach, describe, expect, it, vi } from 'vitest';
import { motionDuration, prefersReducedMotion } from './motion';

const originalMatchMedia = window.matchMedia;

afterEach(() => {
	vi.unstubAllGlobals();
	Object.defineProperty(window, 'matchMedia', { configurable: true, value: originalMatchMedia });
});

describe('motion preferences', () => {
	it('returns false when matchMedia is unavailable', () => {
		vi.stubGlobal('matchMedia', undefined);
		expect(prefersReducedMotion()).toBe(false);
	});

	it('returns false when reduced motion does not match', () => {
		vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({ matches: false }));
		expect(prefersReducedMotion()).toBe(false);
		expect(motionDuration(200)).toBe(200);
	});

	it('returns true and zero duration when reduced motion matches', () => {
		vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({ matches: true }));
		expect(prefersReducedMotion()).toBe(true);
		expect(motionDuration(200)).toBe(0);
	});
});
