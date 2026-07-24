import { get } from 'svelte/store';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock('$lib/api/client', () => ({ api }));

async function loadModules(token: string) {
	// Intentional test boundary: resetModules must create fresh module-level token caches per case.
	const authModule = await import('$lib/stores/auth');
	authModule.auth.update((current) => ({ ...current, token }));
	const statusModule = await import('../status');
	return { ...authModule, ...statusModule };
}

beforeEach(() => {
	vi.resetModules();
	api.get.mockReset();
	api.post.mockReset();
	localStorage.clear();
});

describe('tutorial status token cache', () => {
	it('deduplicates concurrent and completed loads for an unchanged token', async () => {
		api.get.mockResolvedValue({ statuses: { 'admin-compute': 'completed' } });
		const modules = await loadModules('token-a');

		await Promise.all([modules.loadTutorialStatuses(), modules.loadTutorialStatuses()]);
		await modules.loadTutorialStatuses();

		expect(api.get).toHaveBeenCalledTimes(1);
		expect(get(modules.tutorialStatuses)).toEqual({ 'admin-compute': 'completed' });
		expect(get(modules.tutorialStatusesLoaded)).toBe(true);
	});

	it('loads a new token and ignores a late response from the previous token', async () => {
		const gateA = Promise.withResolvers<unknown>();
		const gateB = Promise.withResolvers<unknown>();
		api.get
			.mockReturnValueOnce(gateA.promise)
			.mockReturnValueOnce(gateB.promise);
		const modules = await loadModules('token-a');

		const first = modules.loadTutorialStatuses();
		modules.auth.update((current) => ({ ...current, token: 'token-b' }));
		const second = modules.loadTutorialStatuses();
		gateB.resolve({ statuses: { 'admin-storage': 'dismissed' } });
		await second;
		gateA.resolve({ statuses: { 'admin-compute': 'completed' } });
		await first;

		expect(api.get).toHaveBeenCalledTimes(2);
		expect(get(modules.tutorialStatuses)).toEqual({ 'admin-storage': 'dismissed' });
		expect(get(modules.tutorialStatusesLoaded)).toBe(true);
	});

	it('allows retry after a failed load', async () => {
		api.get
			.mockRejectedValueOnce(new Error('temporary'))
			.mockResolvedValueOnce({ statuses: { 'admin-system': 'completed' } });
		const modules = await loadModules('token-retry');

		await modules.loadTutorialStatuses();
		expect(get(modules.tutorialStatusesLoaded)).toBe(false);
		await modules.loadTutorialStatuses();

		expect(api.get).toHaveBeenCalledTimes(2);
		expect(get(modules.tutorialStatuses)).toEqual({ 'admin-system': 'completed' });
		expect(get(modules.tutorialStatusesLoaded)).toBe(true);
	});
});
