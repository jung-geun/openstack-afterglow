import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import { writable } from 'svelte/store';

const { mockGet } = vi.hoisted(() => ({ mockGet: vi.fn() }));

vi.mock('$lib/api/client', () => ({ api: { get: mockGet } }));
vi.mock('$lib/stores/auth', () => ({
	auth: writable({ token: 'token', projectId: 'project', projectName: 'Project One' }),
	authReady: writable(true),
}));
vi.mock('$lib/utils/autoRefresh.svelte', () => ({
	createAutoRefresh: () => ({ active: false, intervalSeconds: 60, intervalOptions: [30, 60] }),
}));

import Page from '../+page.svelte';

describe('usage loading boundaries', () => {
	it('renders usage stats while best-effort trends remain pending or fail', async () => {
		const stats = Promise.withResolvers<{ range: string; top_instances: unknown[] }>();
		const trend = Promise.withResolvers<unknown>();
		mockGet.mockImplementation((path: string) => path.includes('/metrics/trend') ? trend.promise : stats.promise);

		render(Page);
		await vi.waitFor(() => expect(mockGet).toHaveBeenCalledTimes(2));
		stats.resolve({ range: '7d', top_instances: [] });
		expect(await screen.findByText('인스턴스 없음')).toBeTruthy();
		expect(screen.getByText('추세 메트릭을 불러오는 중...')).toBeTruthy();

		trend.reject(new Error('trend unavailable'));
		await vi.waitFor(() => expect(screen.queryByText('추세 메트릭을 불러오는 중...')).toBeNull());
		expect(screen.getByText('인스턴스 없음')).toBeTruthy();
		expect(screen.getAllByText('메트릭 수집 미설정').length).toBeGreaterThan(0);
	});
});
