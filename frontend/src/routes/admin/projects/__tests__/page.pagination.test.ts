import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { writable } from 'svelte/store';

const { mockGet, mockPrefetch } = vi.hoisted(() => ({
	mockGet: vi.fn(),
	mockPrefetch: vi.fn(),
}));

vi.mock('$lib/api/client', () => ({ api: { get: mockGet, prefetch: mockPrefetch } }));
vi.mock('$lib/stores/auth', () => ({
	auth: writable({ token: 'token', projectId: 'project' }),
}));
vi.mock('$lib/utils/autoRefresh.svelte', () => ({
	createAutoRefresh: () => ({
		active: false,
		intervalSeconds: 60,
		intervalOptions: [30, 60],
	}),
}));

import Page from '../+page.svelte';

describe('admin project marker prefetch', () => {
	beforeEach(() => {
		mockGet.mockReset();
		mockPrefetch.mockReset();
		vi.useFakeTimers();
		vi.stubGlobal('matchMedia', vi.fn(() => ({
			matches: false,
			addEventListener: vi.fn(),
			removeEventListener: vi.fn(),
		})));
		mockGet
			.mockResolvedValueOnce({ items: [], next_marker: 'marker-2' })
			.mockResolvedValueOnce({ items: [], next_marker: null });
		mockPrefetch.mockResolvedValue(undefined);
	});

	afterEach(() => {
		vi.useRealTimers();
		vi.unstubAllGlobals();
	});

	it('uses the exact next-page path for intent and visible navigation', async () => {
		render(Page);
		await vi.advanceTimersByTimeAsync(0);
		const next = await screen.findByRole('button', { name: '다음 →' });

		await fireEvent.pointerEnter(next);
		expect(mockPrefetch).toHaveBeenCalledWith(
			'/api/v1/admin/projects?limit=20&marker=marker-2',
			'token',
			'project',
			expect.objectContaining({ signal: expect.any(AbortSignal) }),
		);

		await fireEvent.click(next);
		await vi.waitFor(() => expect(mockGet).toHaveBeenCalledTimes(2));
		expect(mockGet.mock.calls[1][0]).toBe('/api/v1/admin/projects?limit=20&marker=marker-2');
	});
	it('ignores a late page-size response and does not schedule its marker', async () => {
		const oldRequest = Promise.withResolvers<{ items: Array<{ id: string; name: string; description: string; enabled: boolean }>; next_marker: string }>();
		const newRequest = Promise.withResolvers<{ items: Array<{ id: string; name: string; description: string; enabled: boolean }>; next_marker: string }>();
		mockGet.mockReset()
			.mockReturnValueOnce(oldRequest.promise)
			.mockReturnValueOnce(newRequest.promise);
		mockPrefetch.mockReset().mockResolvedValue(undefined);

		render(Page);
		await vi.waitFor(() => expect(mockGet).toHaveBeenCalledOnce());
		await fireEvent.click(screen.getByRole('button', { name: '10' }));
		await vi.waitFor(() => expect(mockGet).toHaveBeenCalledTimes(2));

		newRequest.resolve({
			items: [{ id: 'new-project', name: 'Newest project', description: '', enabled: true }],
			next_marker: 'new-marker',
		});
		expect(await screen.findByText('Newest project')).toBeTruthy();
		oldRequest.resolve({
			items: [{ id: 'old-project', name: 'Stale project', description: '', enabled: true }],
			next_marker: 'old-marker',
		});
		await vi.advanceTimersByTimeAsync(200);

		expect(screen.queryByText('Stale project')).toBeNull();
		expect(mockPrefetch).toHaveBeenCalledOnce();
		expect(mockPrefetch.mock.calls[0][0]).toBe('/api/v1/admin/projects?limit=10&marker=new-marker');
	});

});
