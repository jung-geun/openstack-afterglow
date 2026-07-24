/**
 * 사용자별 튜토리얼(투어) 진행 이력 — 서버 기록 + 프론트 강조 판정.
 *
 * - 로그인 후 한 번 loadTutorialStatuses() 로 서버 이력을 받아 스토어에 채운다.
 * - 기록이 없는 투어는 "미체험" → 해당 페이지의 튜토리얼 버튼을 강조한다.
 * - 투어 완주(engine 의 'afterglow:tour-complete' 이벤트) → 'completed' 기록.
 * - 사용자가 강조를 무시('나중에') → 'dismissed' 기록. 어느 쪽이든 기록되면 강조 해제.
 */
import { get, writable } from 'svelte/store';

import { api } from '$lib/api/client';
import { auth } from '$lib/stores/auth';

import type { TourId } from './tours';

export type TutorialStatus = 'completed' | 'dismissed';
export type TutorialStatusMap = Partial<Record<TourId, TutorialStatus>>;

export const tutorialStatuses = writable<TutorialStatusMap>({});
// 서버 이력 조회가 최소 1회 성공했는지. 초대 팝오버는 이 값이 true 된 뒤에만 띄워
// 로드 전 빈 맵({}) 상태에서 이미 완료/무시한 사용자에게 초대가 깜빡이는 것을 막는다.
export const tutorialStatusesLoaded = writable(false);

let loadedToken: string | null = null;
let loadingToken: string | null = null;
let loadGeneration = 0;

/** 로그인 사용자의 튜토리얼 이력을 토큰별로 한 번 조회해 스토어에 채운다. */
export async function loadTutorialStatuses(force = false): Promise<void> {
	const { token } = get(auth);
	if (!token) return;
	if (!force && (loadedToken === token || loadingToken === token)) return;

	const generation = ++loadGeneration;
	loadedToken = null;
	loadingToken = token;
	tutorialStatuses.set({});
	tutorialStatusesLoaded.set(false);

	try {
		const res = await api.get<{ statuses: Record<string, TutorialStatus> }>(
			'/api/v1/tutorials/status',
			token,
		);
		if (generation !== loadGeneration || get(auth).token !== token) return;
		tutorialStatuses.set((res?.statuses ?? {}) as TutorialStatusMap);
		loadedToken = token;
		tutorialStatusesLoaded.set(true);
	} catch {
		if (generation !== loadGeneration || get(auth).token !== token) return;
		loadedToken = null;
		tutorialStatusesLoaded.set(false);
	} finally {
		if (generation === loadGeneration) loadingToken = null;
	}
}

/** 특정 투어 상태를 기록. 낙관적으로 스토어를 먼저 갱신해 강조를 즉시 해제한다. */
export async function recordTutorialStatus(tour: TourId, status: TutorialStatus): Promise<void> {
	tutorialStatuses.update((m) => ({ ...m, [tour]: status }));
	const { token } = get(auth);
	if (!token) return;
	try {
		await api.post(`/api/v1/tutorials/${tour}/status`, { status }, token);
	} catch {
		// best-effort: 낙관값 유지, 다음 로드에서 서버값으로 정합.
	}
}

// 투어 완주 이벤트 수신 → completed 기록(버튼/URL 재개 등 모든 완료 경로 공통 처리).
if (typeof window !== 'undefined') {
	window.addEventListener('afterglow:tour-complete', (event) => {
		const tourId = (event as CustomEvent).detail?.tourId as TourId | undefined;
		if (tourId) void recordTutorialStatus(tourId, 'completed');
	});
}
