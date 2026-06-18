import { describe, it, expect, beforeEach, vi } from 'vitest';
import { get } from 'svelte/store';

vi.mock('$lib/api/client', () => ({
	api: {
		get: vi.fn(),
	},
}));

describe('projectNames store', () => {
	beforeEach(() => {
		vi.resetModules();
		vi.clearAllMocks();
	});

	it('초기 상태는 빈 Map', async () => {
		const { projectNames } = await import('../projectNames');
		expect(get(projectNames).size).toBe(0);
	});

	it('load() 첫 호출 시 API 호출 후 Map 채움', async () => {
		const { api } = await import('$lib/api/client');
		const { projectNames } = await import('../projectNames');

		vi.mocked(api.get).mockResolvedValueOnce([
			{ id: 'proj-1', name: '프로젝트 A' },
			{ id: 'proj-2', name: '프로젝트 B' },
		]);

		await projectNames.load('token', 'proj-1');

		const map = get(projectNames);
		expect(map.get('proj-1')).toBe('프로젝트 A');
		expect(map.get('proj-2')).toBe('프로젝트 B');
		expect(api.get).toHaveBeenCalledWith('/api/v1/admin/projects/names', 'token', 'proj-1');
	});

	it('load() 두 번째 호출은 API를 다시 호출하지 않음 (idempotent)', async () => {
		const { api } = await import('$lib/api/client');
		const { projectNames } = await import('../projectNames');

		vi.mocked(api.get).mockResolvedValue([{ id: 'proj-1', name: 'A' }]);

		await projectNames.load('token', 'proj-1');
		await projectNames.load('token', 'proj-1');

		expect(api.get).toHaveBeenCalledTimes(1);
	});

	it('reset() 후 load() 다시 API 호출', async () => {
		const { api } = await import('$lib/api/client');
		const { projectNames } = await import('../projectNames');

		vi.mocked(api.get).mockResolvedValue([{ id: 'proj-1', name: 'A' }]);

		await projectNames.load('token', 'proj-1');
		projectNames.reset();
		await projectNames.load('token', 'proj-1');

		expect(api.get).toHaveBeenCalledTimes(2);
	});

	it('reset() 후 Map이 비워짐', async () => {
		const { api } = await import('$lib/api/client');
		const { projectNames } = await import('../projectNames');

		vi.mocked(api.get).mockResolvedValue([{ id: 'proj-1', name: 'A' }]);
		await projectNames.load('token', 'proj-1');
		expect(get(projectNames).size).toBe(1);

		projectNames.reset();
		expect(get(projectNames).size).toBe(0);
	});

	it('API 실패 시 빈 Map 유지 (예외 무시)', async () => {
		const { api } = await import('$lib/api/client');
		const { projectNames } = await import('../projectNames');

		vi.mocked(api.get).mockRejectedValueOnce(new Error('Network Error'));
		await projectNames.load('token', 'proj-1');

		expect(get(projectNames).size).toBe(0);
	});

	it('subscribe로 Map 변화 감지', async () => {
		const { api } = await import('$lib/api/client');
		const { projectNames } = await import('../projectNames');

		vi.mocked(api.get).mockResolvedValueOnce([{ id: 'p1', name: 'P1' }]);

		const sizes: number[] = [];
		const unsub = projectNames.subscribe((map) => sizes.push(map.size));
		await projectNames.load('t', 'p');
		unsub();

		expect(sizes.at(-1)).toBe(1);
	});
});
