import { writable } from 'svelte/store';

// 배너 등 외부에서 튜토리얼 시나리오 선택 모달을 열 때 사용한다.
export const tutorialLauncherOpen = writable(false);
