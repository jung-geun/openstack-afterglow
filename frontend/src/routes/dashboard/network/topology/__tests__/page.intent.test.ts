import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { writable } from 'svelte/store';

const { mockGet, mockPrefetch } = vi.hoisted(() => ({
	mockGet: vi.fn(),
	mockPrefetch: vi.fn(),
}));

vi.mock('$lib/api/client', () => ({
	api: { get: mockGet, prefetch: mockPrefetch },
	ApiError: class ApiError extends Error { status = 500; },
}));
vi.mock('$lib/stores/auth', () => ({
	auth: writable({ token: 'token', projectId: 'project' }),
}));
vi.mock('$lib/utils/autoRefresh.svelte', () => ({
	createAutoRefresh: () => ({
		active: false,
		intervalSeconds: 30,
		intervalOptions: [10, 15, 30, 60],
	}),
}));
vi.mock('$lib/components/GlobalTopology.svelte', async () => ({
	default: (await import('./_TopologyIntentProbe.svelte')).default,
}));

import Page from '../+page.svelte';

const topology = {
	networks: [],
	subnets: [],
	routers: [],
	ports: [],
	instances: [],
	floating_ips: [],
	load_balancers: [],
};

describe('topology detail intent', () => {
	beforeEach(() => {
		vi.useFakeTimers();
		mockGet.mockResolvedValue(topology);
		mockPrefetch.mockResolvedValue(undefined);
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it('waits 150ms, cancels on leave, and aborts started speculation', async () => {
		render(Page);
		await vi.advanceTimersByTimeAsync(0);
		const instance = await screen.findByRole('button', { name: 'instance intent' });

		await fireEvent.pointerEnter(instance);
		await vi.advanceTimersByTimeAsync(149);
		expect(mockPrefetch).not.toHaveBeenCalled();
		await fireEvent.pointerLeave(instance);
		await vi.advanceTimersByTimeAsync(1);
		expect(mockPrefetch).not.toHaveBeenCalled();

		await fireEvent.pointerEnter(instance);
		await vi.advanceTimersByTimeAsync(150);
		expect(mockPrefetch).toHaveBeenCalledOnce();
		expect(mockPrefetch.mock.calls[0].slice(0, 3)).toEqual([
			'/api/v1/instances/instance-1',
			'token',
			'project',
		]);
		const signal = mockPrefetch.mock.calls[0][3].signal as AbortSignal;
		expect(signal.aborted).toBe(false);
		await fireEvent.pointerLeave(instance);
		expect(signal.aborted).toBe(true);
	});
});
