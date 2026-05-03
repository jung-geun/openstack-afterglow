import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import { flushSync, tick } from 'svelte';
import AutoRefreshWrapper from './_AutoRefreshWrapper.svelte';

const storage: Record<string, string> = {};
vi.stubGlobal('localStorage', {
	getItem: (key: string) => storage[key] ?? null,
	setItem: (key: string, val: string) => {
		storage[key] = val;
	},
	removeItem: (key: string) => {
		delete storage[key];
	},
});

describe('createAutoRefresh (via component)', () => {
	beforeEach(() => {
		Object.keys(storage).forEach((k) => delete storage[k]);
		Object.defineProperty(document, 'hidden', { get: () => false, configurable: true });
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it('defaultActive=false 이면 active가 false로 렌더링', () => {
		render(AutoRefreshWrapper, { defaultActive: false, invokeOnMount: false });
		flushSync();
		expect(screen.getByTestId('active').textContent).toBe('false');
	});

	it('defaultActive=true 이면 active가 true로 렌더링', () => {
		render(AutoRefreshWrapper, { defaultActive: true, invokeOnMount: false });
		flushSync();
		expect(screen.getByTestId('active').textContent).toBe('true');
	});

	it('defaultInterval이 interval로 렌더링', () => {
		render(AutoRefreshWrapper, { defaultInterval: 15, defaultActive: false });
		flushSync();
		expect(screen.getByTestId('interval').textContent).toBe('15');
	});

	it('localStorage에서 저장된 active 상태 복원', async () => {
		storage['autoRefresh.test-key.active'] = 'false';
		render(AutoRefreshWrapper, { defaultActive: true, invokeOnMount: false });
		// $effect가 microtask로 실행됨 — tick()으로 스케줄러 플러시
		await tick();
		flushSync();
		expect(screen.getByTestId('active').textContent).toBe('false');
	});

	it('localStorage에서 저장된 interval 복원', async () => {
		storage['autoRefresh.test-key.interval'] = '60';
		render(AutoRefreshWrapper, { defaultInterval: 30, defaultActive: false });
		await tick();
		flushSync();
		expect(screen.getByTestId('interval').textContent).toBe('60');
	});

	it('active=true이면 setInterval이 호출됨', async () => {
		vi.useFakeTimers();
		const setIntervalSpy = vi.spyOn(globalThis, 'setInterval');
		render(AutoRefreshWrapper, { defaultActive: true, invokeOnMount: false, defaultInterval: 30 });
		await tick();
		flushSync();
		expect(setIntervalSpy).toHaveBeenCalled();
	});

	it('active=false이면 setInterval 호출 안 함', async () => {
		vi.useFakeTimers();
		const setIntervalSpy = vi.spyOn(globalThis, 'setInterval');
		render(AutoRefreshWrapper, { defaultActive: false, invokeOnMount: false });
		await tick();
		flushSync();
		expect(setIntervalSpy).not.toHaveBeenCalled();
	});

	it('fn이 interval마다 호출됨', async () => {
		vi.useFakeTimers();
		const fn = vi.fn();
		render(AutoRefreshWrapper, { fn, defaultActive: true, invokeOnMount: false, defaultInterval: 10 });
		await tick();
		flushSync();
		vi.advanceTimersByTime(10_000);
		expect(fn).toHaveBeenCalled();
	});

	it('visibilitychange: hidden 시 clearInterval 호출', async () => {
		vi.useFakeTimers();
		const clearIntervalSpy = vi.spyOn(globalThis, 'clearInterval');
		render(AutoRefreshWrapper, { defaultActive: true, invokeOnMount: false });
		await tick();
		flushSync();

		Object.defineProperty(document, 'hidden', { get: () => true, configurable: true });
		document.dispatchEvent(new Event('visibilitychange'));
		expect(clearIntervalSpy).toHaveBeenCalled();
	});
});
