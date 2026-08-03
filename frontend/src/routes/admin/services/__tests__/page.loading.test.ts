import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { writable } from 'svelte/store';

const { mockGet, autoRefreshCallback } = vi.hoisted(() => ({
	mockGet: vi.fn(),
	autoRefreshCallback: { current: null as (() => Promise<void>) | null },
}));

vi.mock('$lib/api/client', () => ({ api: { get: mockGet } }));
vi.mock('$lib/stores/auth', () => ({
	auth: writable({ token: 'token', projectId: 'project' }),
}));
vi.mock('$lib/config/site', () => ({
	siteConfig: writable({
		services: { magnum: true, manila: true, zun: true },
	}),
}));
vi.mock('$lib/utils/autoRefresh.svelte', () => ({
	createAutoRefresh: (callback: () => Promise<void>) => {
		autoRefreshCallback.current = callback;
		return {
			active: false,
			intervalSeconds: 15,
			intervalOptions: [10, 15, 30, 60],
		};
	},
}));

import Page from '../+page.svelte';

describe('admin services loading graph', () => {
	it('loads only the active category and starts an idle tab on intent', async () => {
		const compute = Promise.withResolvers<Record<string, unknown>>();
		const network = Promise.withResolvers<Record<string, unknown>>();
		let networkCalls = 0;
		mockGet.mockImplementation((path: string) => {
			if (path.endsWith('category=compute')) return compute.promise;
			if (path.endsWith('category=network')) {
				networkCalls += 1;
				return networkCalls === 1 ? network.promise : Promise.resolve({ network: [] });
			}
			throw new Error(`unexpected GET ${path}`);
		});

		render(Page);
		await vi.waitFor(() => expect(mockGet).toHaveBeenCalledOnce());
		expect(mockGet.mock.calls[0][0]).toBe('/api/v1/admin/services?category=compute');
		expect(screen.getAllByText('—')).toHaveLength(8);

		await fireEvent.pointerEnter(screen.getByRole('button', { name: /Network/ }));
		expect(mockGet).toHaveBeenCalledTimes(2);
		expect(mockGet.mock.calls[1][0]).toBe('/api/v1/admin/services?category=network');

		compute.resolve({ compute: [] });
		network.resolve({ network: [] });
		await vi.waitFor(() => expect(screen.getAllByText('—')).toHaveLength(7));

		await fireEvent.click(screen.getByRole('button', { name: /Network/ }));
		expect(mockGet).toHaveBeenCalledTimes(2);

		await autoRefreshCallback.current?.();
		expect(mockGet).toHaveBeenCalledTimes(3);
		expect(mockGet.mock.calls[2][0]).toBe('/api/v1/admin/services?category=network');
		expect(mockGet.mock.calls[2][3]).toEqual({ refresh: true });

		await fireEvent.click(screen.getByRole('button', { name: '새로고침' }));
		await vi.waitFor(() => expect(mockGet).toHaveBeenCalledTimes(4));
		expect(mockGet.mock.calls[3][0]).toBe('/api/v1/admin/services?category=network');
	});
});
