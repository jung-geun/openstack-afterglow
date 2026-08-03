import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createIntentPrefetchScheduler } from '../intentPrefetch';

beforeEach(() => {
	vi.useFakeTimers();
	Reflect.deleteProperty(window, 'requestIdleCallback');
	Reflect.deleteProperty(window, 'cancelIdleCallback');
});

afterEach(() => {
	vi.useRealTimers();
});

describe('intent prefetch scheduler', () => {
	it('uses one 200ms fallback and immediate intent reuses the same speculation', async () => {
		const run = vi.fn();
		const scheduler = createIntentPrefetchScheduler();
		scheduler.schedule('next', run);
		expect(vi.getTimerCount()).toBe(1);

		scheduler.intent('next', run);
		expect(run).toHaveBeenCalledOnce();
		vi.advanceTimersByTime(200);
		expect(run).toHaveBeenCalledOnce();
	});

	it('uses requestIdleCallback instead of also scheduling a timeout', () => {
		const idle = { callback: null as (() => void) | null };
		Object.assign(window, {
			requestIdleCallback: vi.fn((callback: () => void) => {
				idle.callback = callback;
				return 7;
			}),
			cancelIdleCallback: vi.fn(),
		});
		const run = vi.fn();
		const scheduler = createIntentPrefetchScheduler();
		scheduler.schedule('next', run);

		expect(window.requestIdleCallback).toHaveBeenCalledWith(expect.any(Function), { timeout: 1_000 });
		expect(vi.getTimerCount()).toBe(0);
		idle.callback?.();
		expect(run).toHaveBeenCalledOnce();
	});

	it('cancels and aborts superseded speculation', () => {
		const signals: AbortSignal[] = [];
		const scheduler = createIntentPrefetchScheduler();
		scheduler.schedule('old', (signal) => { signals.push(signal); });
		scheduler.intent('old', (signal) => { signals.push(signal); });
		expect(signals[0].aborted).toBe(false);

		scheduler.schedule('new', vi.fn());
		expect(signals[0].aborted).toBe(true);
		scheduler.cancel();
		expect(vi.getTimerCount()).toBe(0);
	});
});
