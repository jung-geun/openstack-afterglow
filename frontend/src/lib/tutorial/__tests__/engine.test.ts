import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { clearPersistedTour, readPersistedTour, waitForElement } from '../engine';
import { getTour, isTourId, tours, TOUR_STORAGE_KEY } from '../tours';

beforeEach(() => {
	sessionStorage.clear();
	document.body.innerHTML = '';
});

afterEach(() => {
	sessionStorage.clear();
	document.body.innerHTML = '';
});

describe('tour definitions', () => {
	it('declares unique ids and valid data-tour anchors', () => {
		const ids = tours.map((tour) => tour.id);
		expect(new Set(ids).size).toBe(ids.length);
		for (const tour of tours) {
			expect(tour.steps.length).toBeGreaterThan(0);
			// 첫 step은 시작 라우트를 가져야 어디서 시작해도 올바른 페이지로 이동한다
			expect(tour.steps[0].route).toBeTruthy();
			for (const step of tour.steps) {
				expect(step.element).toMatch(/^\[data-tour="[a-z-]+"\]$/);
				expect(step.title.length).toBeGreaterThan(0);
				expect(step.description.length).toBeGreaterThan(0);
			}
		}
	});

	it('resolves tour ids strictly', () => {
		expect(isTourId('vm-create')).toBe(true);
		expect(isTourId('volume')).toBe(true);
		expect(isTourId('drover')).toBe(true);
		expect(isTourId('admin')).toBe(false);
		expect(getTour('volume')?.steps[0].route).toBe('/dashboard/volumes');
		expect(getTour('nope')).toBeNull();
	});
});

describe('tour persistence', () => {
	it('roundtrips a valid tour state', () => {
		sessionStorage.setItem(TOUR_STORAGE_KEY, JSON.stringify({ tourId: 'drover', stepIndex: 2 }));
		expect(readPersistedTour()).toEqual({ tourId: 'drover', stepIndex: 2 });
		clearPersistedTour();
		expect(readPersistedTour()).toBeNull();
	});

	it('rejects unknown tours, out-of-range steps, and corrupt payloads', () => {
		sessionStorage.setItem(TOUR_STORAGE_KEY, JSON.stringify({ tourId: 'unknown', stepIndex: 0 }));
		expect(readPersistedTour()).toBeNull();
		sessionStorage.setItem(TOUR_STORAGE_KEY, JSON.stringify({ tourId: 'volume', stepIndex: 99 }));
		expect(readPersistedTour()).toBeNull();
		sessionStorage.setItem(TOUR_STORAGE_KEY, 'not-json');
		expect(readPersistedTour()).toBeNull();
	});
});

describe('waitForElement', () => {
	it('returns an element that appears after polling starts', async () => {
		setTimeout(() => {
			const el = document.createElement('div');
			el.dataset.tour = 'late-anchor';
			document.body.appendChild(el);
		}, 30);
		const found = await waitForElement('[data-tour="late-anchor"]', 500, 10);
		expect(found).not.toBeNull();
		expect(found?.dataset.tour).toBe('late-anchor');
	});

	it('returns null when the element never appears', async () => {
		const found = await waitForElement('[data-tour="never"]', 80, 10);
		expect(found).toBeNull();
	});
});
