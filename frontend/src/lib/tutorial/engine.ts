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
// 동시에 여러 showStep이 진행되지 않도록 최신 호출만 유효화한다.
let showSerial = 0;

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
		// 하이라이트 밖(dim 영역) 클릭으로 투어가 사라지지 않게 한다. ESC/× 버튼으로만 종료.
		allowClose: false,
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

/**
 * 라우트 변경 후 현재 스텝을 다시 앵커링한다.
 * 대상 요소가 사라졌으면(모달 닫힘 등) 유효한 이전 스텝으로 되감는다.
 */
export function refreshTourAnchor(): void {
	if (!driverInstance || !currentTour) return;
	void showStep(currentIndex);
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
	const serial = ++showSerial;
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

	const el = await waitForElement(step.element, step.waitTimeoutMs ?? (index === 0 ? 8000 : 3000));
	// 대기 중 사용자가 투어를 닫았거나 더 새로운 스텝 전환이 시작된 경우
	if (d !== driverInstance || currentTour !== tour || serial !== showSerial) return;
	if (!el) {
		// 요소가 사라졌으면(페이지 이동으로 모달이 닫힘 등) 이전 스텝으로 되감는다.
		if (index > 0) {
			void showStep(index - 1);
		} else {
			stopTour();
		}
		return;
	}

	const isLast = index === tour.steps.length - 1;
	const clickDriven = step.advanceOn === 'click';

	if (clickDriven) {
		// 진행 트리거는 하이라이트 요소와 다를 수 있다(예: 폼 전체 하이라이트 + 생성 버튼 클릭).
		// document 캡처 위임: 하이라이트 표시 전에 무장되고, 대상 노드가 리렌더로 교체돼도 동작한다.
		const triggerSelector = step.advanceElement ?? step.element;
		const handler = (event: Event) => {
			const target = event.target as Element | null;
			if (!target?.closest?.(triggerSelector)) return;
			cleanupClickListener();
			void moveTo(index + 1);
		};
		document.addEventListener('click', handler, { capture: true });
		clickCleanup = () => document.removeEventListener('click', handler, { capture: true });
	}

	d.highlight({
		element: step.element,
		popover: {
			title: `${step.title} (${index + 1}/${tour.steps.length})`,
			description: step.description,
			showButtons: clickDriven
				? ['close']
				: index === 0
					? ['next', 'close']
					: ['next', 'previous', 'close'],
			nextBtnText: isLast ? '완료' : '다음',
		},
	});
}

function cleanupClickListener(): void {
	clickCleanup?.();
	clickCleanup = null;
}

export function stopTour(): void {
	if (stopping) return;
	stopping = true;
	try {
		showSerial += 1;
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
