import { goto } from '$app/navigation';
import type { Driver } from 'driver.js';
import { getTour, TOUR_STORAGE_KEY, type TourDefinition, type TourId } from './tours';

export interface PersistedTourState {
	tourId: TourId;
	stepIndex: number;
}

export function readPersistedTour(): PersistedTourState | null {
	if (typeof sessionStorage === 'undefined') return null;
	try {
		const raw = sessionStorage.getItem(TOUR_STORAGE_KEY);
		if (!raw) return null;
		const parsed = JSON.parse(raw) as PersistedTourState;
		const tour = getTour(parsed.tourId);
		if (!tour || !Number.isInteger(parsed.stepIndex)) return null;
		if (parsed.stepIndex < 0 || parsed.stepIndex >= tour.steps.length) return null;
		return parsed;
	} catch {
		return null;
	}
}

export function clearPersistedTour(): void {
	if (typeof sessionStorage === 'undefined') return;
	sessionStorage.removeItem(TOUR_STORAGE_KEY);
}

function persistTour(tourId: TourId, stepIndex: number): void {
	if (typeof sessionStorage === 'undefined') return;
	sessionStorage.setItem(TOUR_STORAGE_KEY, JSON.stringify({ tourId, stepIndex }));
}

export async function waitForElement(
	selector: string,
	timeoutMs = 8000,
	pollMs = 120,
): Promise<HTMLElement | null> {
	const deadline = Date.now() + timeoutMs;
	for (;;) {
		const el = document.querySelector<HTMLElement>(selector);
		if (el && el.getClientRects().length > 0) return el;
		if (Date.now() >= deadline) return el;
		await new Promise((resolve) => setTimeout(resolve, pollMs));
	}
}

let driverInstance: Driver | null = null;
let currentTour: TourDefinition | null = null;
let currentIndex = 0;
let stopping = false;
let clickCleanup: (() => void) | null = null;

export function isTourActive(): boolean {
	return driverInstance !== null;
}

export async function startTour(tourId: TourId, fromStep = 0): Promise<boolean> {
	if (typeof window === 'undefined') return false;
	const tour = getTour(tourId);
	if (!tour) return false;
	stopTour();
	const { driver } = await import('driver.js');
	currentTour = tour;
	driverInstance = driver({
		animate: true,
		overlayOpacity: 0.65,
		stagePadding: 6,
		allowClose: true,
		disableActiveInteraction: false,
		popoverClass: 'afterglow-tour',
		nextBtnText: '다음',
		prevBtnText: '이전',
		onNextClick: () => void moveTo(currentIndex + 1),
		onPrevClick: () => void moveTo(currentIndex - 1),
		onCloseClick: () => stopTour(),
		onDestroyStarted: () => stopTour(),
	});
	const startIndex = Math.min(Math.max(fromStep, 0), tour.steps.length - 1);
	await showStep(startIndex);
	return true;
}

async function moveTo(index: number): Promise<void> {
	if (!currentTour) return;
	if (index < 0) return;
	if (index >= currentTour.steps.length) {
		stopTour();
		return;
	}
	await showStep(index);
}

async function showStep(index: number): Promise<void> {
	const tour = currentTour;
	const d = driverInstance;
	if (!tour || !d) return;
	cleanupClickListener();
	currentIndex = index;
	const step = tour.steps[index];
	persistTour(tour.id, index);

	if (step.route && window.location.pathname !== step.route) {
		try {
			await goto(step.route);
		} catch {
			// mockup 레이어의 beforeNavigate가 쿼리를 붙여 재시도할 수 있음 — 요소 대기로 흡수
		}
	}

	const el = await waitForElement(step.element, step.waitTimeoutMs);
	// 대기 중 사용자가 투어를 닫았거나 새 투어가 시작된 경우
	if (d !== driverInstance || currentTour !== tour) return;
	if (!el) {
		stopTour();
		return;
	}

	const isLast = index === tour.steps.length - 1;
	d.highlight({
		element: step.element,
		popover: {
			title: `${step.title} (${index + 1}/${tour.steps.length})`,
			description: step.description,
			showButtons:
				step.advanceOn === 'click'
					? ['close']
					: index === 0
						? ['next', 'close']
						: ['next', 'previous', 'close'],
			nextBtnText: isLast ? '완료' : '다음',
		},
	});

	if (step.advanceOn === 'click') {
		const handler = () => {
			cleanupClickListener();
			void moveTo(index + 1);
		};
		el.addEventListener('click', handler, { once: true, capture: true });
		clickCleanup = () => el.removeEventListener('click', handler, { capture: true });
	}
}

function cleanupClickListener(): void {
	clickCleanup?.();
	clickCleanup = null;
}

export function stopTour(): void {
	if (stopping) return;
	stopping = true;
	try {
		cleanupClickListener();
		clearPersistedTour();
		const d = driverInstance;
		driverInstance = null;
		currentTour = null;
		currentIndex = 0;
		d?.destroy();
	} finally {
		stopping = false;
	}
}
