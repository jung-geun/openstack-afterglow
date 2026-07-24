import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { writable } from 'svelte/store';

const { mockGet, mockPrefetch } = vi.hoisted(() => ({ mockGet: vi.fn(), mockPrefetch: vi.fn() }));

vi.mock('$lib/api/client', () => ({
	api: { get: mockGet, prefetch: mockPrefetch, patch: vi.fn(), post: vi.fn(), delete: vi.fn() },
	ApiError: class ApiError extends Error { status = 500; },
}));
vi.mock('$lib/stores/auth', () => ({ auth: writable({ token: 'token', projectId: 'project' }) }));
vi.mock('$lib/stores/projectNames', () => ({ projectNames: { load: vi.fn() } }));
vi.mock('$lib/utils/autoRefresh.svelte', () => ({
	createAutoRefresh: () => ({ active: false, intervalSeconds: 30, intervalOptions: [15, 30, 60] }),
}));
vi.mock('$lib/components/admin/images/AdminImagesTable.svelte', async () => ({
	default: (await import('./_AdminImagesTableProbe.svelte')).default,
}));

import Page from '../+page.svelte';

describe('admin image pagination prefetch', () => {
	beforeEach(() => {
		mockGet.mockReset();
		mockPrefetch.mockReset();
		vi.useFakeTimers();
		vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
		mockGet
			.mockResolvedValueOnce({ items: [{ id: 'image-1', name: 'Image', status: 'active', visibility: 'private' }], next_marker: 'marker-2' })
			.mockResolvedValueOnce({ items: [], next_marker: null });
		mockPrefetch.mockResolvedValue(undefined);
	});

	afterEach(() => {
		vi.useRealTimers();
		vi.unstubAllGlobals();
	});

	it('uses the same canonical path for intent and the visible next-page load', async () => {
		render(Page);
		await vi.advanceTimersByTimeAsync(0);
		const next = await screen.findByRole('button', { name: '다음 이미지' });

		await fireEvent.pointerEnter(next);
		expect(mockPrefetch).toHaveBeenCalledOnce();
		expect(mockPrefetch.mock.calls[0].slice(0, 3)).toEqual([
			'/api/v1/admin/images?limit=20&marker=marker-2',
			'token',
			'project',
		]);
		const signal = mockPrefetch.mock.calls[0][3].signal as AbortSignal;

		await fireEvent.click(next);
		expect(signal.aborted).toBe(true);
		await vi.waitFor(() => expect(mockGet).toHaveBeenCalledTimes(2));
		expect(mockGet.mock.calls[1][0]).toBe('/api/v1/admin/images?limit=20&marker=marker-2');
	});
	it('keeps the newest page-size result and schedules only its marker when an older request settles late', async () => {
		const oldRequest = Promise.withResolvers<{ items: Array<{ id: string; name: string; status: string; visibility: string }>; next_marker: string }>();
		const newRequest = Promise.withResolvers<{ items: Array<{ id: string; name: string; status: string; visibility: string }>; next_marker: string }>();
		mockGet.mockReset()
			.mockReturnValueOnce(oldRequest.promise)
			.mockReturnValueOnce(newRequest.promise);
		mockPrefetch.mockReset().mockResolvedValue(undefined);

		render(Page);
		await vi.waitFor(() => expect(mockGet).toHaveBeenCalledOnce());
		await fireEvent.click(screen.getByRole('button', { name: '10' }));
		await vi.waitFor(() => expect(mockGet).toHaveBeenCalledTimes(2));

		newRequest.resolve({
			items: [{ id: 'new-image', name: 'Newest image', status: 'active', visibility: 'private' }],
			next_marker: 'new-marker',
		});
		expect(await screen.findByText('Newest image')).toBeTruthy();
		oldRequest.resolve({
			items: [{ id: 'old-image', name: 'Stale image', status: 'active', visibility: 'private' }],
			next_marker: 'old-marker',
		});
		await vi.advanceTimersByTimeAsync(200);

		expect(screen.queryByText('Stale image')).toBeNull();
		expect(mockPrefetch).toHaveBeenCalledOnce();
		expect(mockPrefetch.mock.calls[0][0]).toBe('/api/v1/admin/images?limit=10&marker=new-marker');
	});

});
