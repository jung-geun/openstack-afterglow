import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { writable } from 'svelte/store';

// --- module mocks (must be declared before static imports) ---

vi.mock('$env/dynamic/public', () => ({ env: { PUBLIC_API_BASE: 'http://localhost:8000' } }));

// Use vi.hoisted so mockGet is available inside the vi.mock factory (which is hoisted)
const { mockGet } = vi.hoisted(() => ({ mockGet: vi.fn() }));
vi.mock('$lib/api/client', () => ({
	api: { get: mockGet },
}));

vi.mock('$lib/stores/auth', () => ({
	auth: writable({ token: 'test-token', projectId: 'test-project' }),
}));

vi.mock('$lib/utils/autoRefresh.svelte', () => ({
	createAutoRefresh: () => ({ active: false, intervalSeconds: 30, intervalOptions: [15, 30, 60] }),
}));

import ActivityLogTable from '../ActivityLogTable.svelte';

// ---------------------------------------------------------------------------

beforeEach(() => {
	vi.clearAllMocks();
});

afterEach(() => {
	vi.useRealTimers();
});

describe('ActivityLogTable', () => {
	it('empty response renders empty message', async () => {
		mockGet.mockResolvedValue([]);

		render(ActivityLogTable, { props: { endpoint: '/api/v1/test/activity', storageKey: 'test' } });

		const msg = await screen.findByText('활동 없음');
		expect(msg).toBeTruthy();
	});

	it('single log row renders action correctly', async () => {
		const now = new Date().toISOString();
		mockGet.mockResolvedValue([
			{
				id: 1,
				action: 'volume.create',
				status: 'success',
				resource_type: 'volume',
				resource_name: 'my-vol',
				resource_id: null,
				created_at: now,
				username: 'user1',
				project_id: 'proj-1',
				user_id: 'u1',
				error_message: null,
				extra: null,
			},
		]);

		render(ActivityLogTable, {
			props: { endpoint: '/api/v1/test/activity', storageKey: 'test', showUser: true },
		});

		const cell = await screen.findByText('volume.create');
		expect(cell).toBeTruthy();
	});

	it('failed status shows error expand button', async () => {
		const now = new Date().toISOString();
		mockGet.mockResolvedValue([
			{
				id: 2,
				action: 'volume.delete',
				status: 'failed',
				resource_type: 'volume',
				resource_name: 'bad-vol',
				resource_id: null,
				created_at: now,
				username: 'user2',
				project_id: 'proj-1',
				user_id: 'u2',
				error_message: 'disk quota exceeded',
				extra: null,
			},
		]);

		render(ActivityLogTable, { props: { endpoint: '/api/v1/test/activity', storageKey: 'test' } });

		const btn = await screen.findByText('상세');
		expect(btn).toBeTruthy();
	});
	it('debounces filters, aborts the superseded request, and ignores its late response', async () => {
		vi.useFakeTimers();
		const first = Promise.withResolvers<unknown[]>();
		const second = Promise.withResolvers<unknown[]>();
		mockGet
			.mockImplementationOnce(() => first.promise)
			.mockImplementationOnce(() => second.promise);
		render(ActivityLogTable, { props: { endpoint: '/api/v1/test/activity', storageKey: 'test' } });

		await vi.advanceTimersByTimeAsync(250);
		expect(mockGet).toHaveBeenCalledOnce();
		const firstSignal = mockGet.mock.calls[0][3].signal as AbortSignal;

		await fireEvent.input(screen.getByPlaceholderText('액션 필터 (예: instance.create)'), {
			target: { value: 'instance.create' },
		});
		await vi.advanceTimersByTimeAsync(249);
		expect(mockGet).toHaveBeenCalledOnce();
		expect(firstSignal.aborted).toBe(true);
		await vi.advanceTimersByTimeAsync(1);
		expect(mockGet).toHaveBeenCalledTimes(2);

		second.resolve([{
			id: 2,
			action: 'instance.create',
			status: 'success',
			resource_type: 'instance',
			resource_name: 'new',
			resource_id: null,
			created_at: new Date().toISOString(),
			username: 'user',
			project_id: 'project',
			user_id: 'user',
			error_message: null,
			extra: null,
		}]);
		await vi.advanceTimersByTimeAsync(0);
		expect(screen.getByText('instance.create')).toBeTruthy();

		first.resolve([{
			id: 1,
			action: 'stale.action',
			status: 'success',
			resource_type: 'instance',
			resource_name: 'stale',
			resource_id: null,
			created_at: new Date().toISOString(),
			username: 'user',
			project_id: 'project',
			user_id: 'user',
			error_message: null,
			extra: null,
		}]);
		await vi.advanceTimersByTimeAsync(0);
		expect(screen.queryByText('stale.action')).toBeNull();
	});

});
