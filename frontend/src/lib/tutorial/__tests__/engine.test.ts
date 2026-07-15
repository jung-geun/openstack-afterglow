import { get } from 'svelte/store';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { setBetaFeature } from '$lib/stores/betaFeatures';
import { sidebarOpen } from '$lib/stores/sidebar';
import { clearPersistedTour, readPersistedTour, waitForElement } from '../engine';
import { getTour, isTourId, tours, TOUR_STORAGE_KEY } from '../tours';

const originalInnerWidth = window.innerWidth;

beforeEach(() => {
	sessionStorage.clear();
	document.body.innerHTML = '';
	sidebarOpen.close();
});

afterEach(() => {
	vi.useRealTimers();
	sessionStorage.clear();
	document.body.innerHTML = '';
	sidebarOpen.close();
	Object.defineProperty(window, 'innerWidth', { value: originalInnerWidth, configurable: true });
});

describe('tour definitions', () => {
	it('declares unique ids and valid data-tour anchors', () => {
		const ids = tours.map((tour) => tour.id);
		expect(new Set(ids).size).toBe(ids.length);
		for (const { id } of tours) {
			const tour = getTour(id);
			expect(tour).not.toBeNull();
			expect(tour!.steps.length).toBeGreaterThan(0);
			// 첫 step은 시작 라우트를 가져야 어디서 시작해도 올바른 페이지로 이동한다
			expect(tour!.steps[0].route).toBeTruthy();
			for (const step of tour!.steps) {
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

	it('vm-create 투어는 libraryConsume 베타에 따라 라이브러리 단계를 넣고 뺀다', () => {
		try {
			setBetaFeature('libraryConsume', false);
			const withoutLib = getTour('vm-create')!;
			expect(withoutLib.steps).toHaveLength(6);
			expect(withoutLib.steps.some((step) => step.title.includes('라이브러리'))).toBe(false);

			setBetaFeature('libraryConsume', true);
			const withLib = getTour('vm-create')!;
			expect(withLib.steps).toHaveLength(7);
			const libStep = withLib.steps.find((step) => step.title.includes('라이브러리'));
			expect(libStep).toBeTruthy();
			// 위저드가 실제로 해당 단계를 노출하지 않으면(비 Ubuntu 이미지) 런타임에 건너뛴다
			expect(libStep!.skipIf).toBeTypeOf('function');
			expect(libStep!.skipIf!()).toBe(true); // 스텝퍼가 없는 DOM에서는 건너뛴다
		} finally {
			setBetaFeature('libraryConsume', false);
		}
	});

	it('vm-create 투어는 raw 위저드 단계와 팝오버 진행 방식을 매핑한다', () => {
		try {
			setBetaFeature('libraryConsume', true);
			const tour = getTour('vm-create')!;
			const expected = [
				{ title: '이미지 선택', wizardStep: 1, advanceOn: 'wizard' },
				{ title: '플레이버 선택', wizardStep: 2, advanceOn: 'wizard' },
				{ title: '라이브러리 (베타)', wizardStep: 3, advanceOn: 'wizard' },
				{ title: '기본 설정 확인', wizardStep: 5, advanceOn: 'wizard' },
				{ title: '배포', wizardStep: 6, advanceOn: 'click' },
			] as const;

			for (const mapping of expected) {
				const step = tour.steps.find((candidate) => candidate.title === mapping.title);
				expect(step).toMatchObject({
					wizardStep: mapping.wizardStep,
					advanceOn: mapping.advanceOn,
				});
				expect(step?.backElement).toBeUndefined();
			}

			const imageStep = tour.steps.find((step) => step.title === '이미지 선택');
			expect(imageStep?.cancelElement).toBe('[data-tour="wizard-cancel"]');
			expect(imageStep?.readyElement).toBe('[data-tour="wizard-body"]');
			const deployStep = tour.steps.find((step) => step.title === '배포');
			expect(deployStep?.advanceElement).toBe('[data-tour="wizard-next"]');
		} finally {
			setBetaFeature('libraryConsume', false);
		}
	});

	it('모바일에서 vm-create 첫 step 준비 시 사이드바를 연다', async () => {
		vi.useFakeTimers();
		Object.defineProperty(window, 'innerWidth', { value: 375, configurable: true });
		const prepare = getTour('vm-create')!.steps[0].prepare!;

		const preparing = prepare();
		expect(get(sidebarOpen)).toBe(true);
		await vi.advanceTimersByTimeAsync(250);
		await preparing;
	});

	it('데스크톱에서 vm-create 첫 step 준비 시 사이드바를 열지 않는다', async () => {
		Object.defineProperty(window, 'innerWidth', { value: 1280, configurable: true });
		const prepare = getTour('vm-create')!.steps[0].prepare!;

		await prepare();
		expect(get(sidebarOpen)).toBe(false);
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
