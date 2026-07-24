import { fireEvent, render, screen } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { auth } from '../auth';
import { DEFAULT_BETA_FEATURES, betaFeatures } from '../betaFeatures';
import { resetWizard } from '../wizard';

const { api } = vi.hoisted(() => ({ api: { get: vi.fn(), post: vi.fn() } }));
vi.mock('$app/navigation', () => ({ goto: vi.fn() }));
vi.mock('$lib/api/client', () => ({
	api,
	ApiError: class ApiError extends Error {},
	getBaseUrl: () => '',
}));
vi.mock('$lib/mockup/transport', () => ({ maybeMockInstanceCreateStream: () => null }));

import VmCreateStoreLoadWrapper from './_VmCreateStoreLoadWrapper.svelte';

function deferred<T>() {
	let resolve!: (value: T) => void;
	let reject!: (reason?: unknown) => void;
	const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
	return { promise, resolve, reject };
}

const image = { id: 'image-1', name: 'Ubuntu', status: 'active' };
const flavor = { id: 'flavor-1', name: 'small', vcpus: 1, ram: 1024, disk: 20 };

describe('VM create option loading boundaries', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		resetWizard();
		betaFeatures.set(DEFAULT_BETA_FEATURES);
		auth.set({ token: 'token', refreshToken: null, accessExpiresAt: null, userId: 'user', username: 'user', projectId: 'project', projectName: 'project', availableProjects: [], roles: [], isSystemAdmin: false, federated: false });
	});

	it('prefetches configuration after boot options settle without delaying step 1', async () => {
		const images = deferred<typeof image[]>();
		const volumes = deferred<unknown[]>();
		const flavors = deferred<typeof flavor[]>();
		const quota = deferred<unknown>();
		const configuration = deferred<unknown[]>();
		api.get.mockImplementation((path: string) => {
			if (path === '/api/v1/images') return images.promise;
			if (path === '/api/v1/volumes') return volumes.promise;
			if (path === '/api/v1/flavors') return flavors.promise;
			if (path === '/api/v1/dashboard/quotas') return quota.promise;
			if (['/api/v1/networks', '/api/v1/keypairs', '/api/v1/security-groups', '/api/v1/networks/default', '/api/v1/file-storage'].includes(path)) return configuration.promise;
			return Promise.resolve([]);
		});
		render(VmCreateStoreLoadWrapper);
		await fireEvent.click(screen.getByTestId('init'));
		expect(api.get.mock.calls.map(([path]) => path)).toEqual(expect.arrayContaining([
			'/api/v1/images', '/api/v1/volumes', '/api/v1/flavors', '/api/v1/dashboard/quotas',
		]));
		expect(api.get.mock.calls.map(([path]) => path)).not.toEqual(expect.arrayContaining(['/api/v1/networks', '/api/v1/file-storage', '/api/v1/libraries']));

		images.resolve([image]);
		await Promise.resolve();
		expect(screen.getByTestId('loading').textContent).toBe('loading');
		volumes.resolve([]);
		await vi.waitFor(() => expect(api.get.mock.calls.map(([path]) => path)).toEqual(expect.arrayContaining([
			'/api/v1/networks', '/api/v1/keypairs', '/api/v1/security-groups', '/api/v1/networks/default', '/api/v1/file-storage',
		])));
		expect(screen.getByTestId('loading').textContent).toBe('ready');
		configuration.resolve([]);
		flavors.resolve([flavor]);
		quota.resolve({});
	});

	it('starts every public configuration endpoint together at step 5 without making file storage a gate', async () => {
		api.get.mockImplementation((path: string) => {
			if (path === '/api/v1/images') return Promise.resolve([image]);
			if (path === '/api/v1/volumes') return Promise.resolve([]);
			if (path === '/api/v1/flavors') return Promise.resolve([flavor]);
			if (path === '/api/v1/dashboard/quotas') return Promise.resolve({});
			if (path === '/api/v1/file-storage') return Promise.reject(new Error('optional'));
			return Promise.resolve([]);
		});
		render(VmCreateStoreLoadWrapper);
		await fireEvent.click(screen.getByTestId('init'));
		await Promise.resolve();
		await fireEvent.click(screen.getByTestId('step-five'));
		const paths = api.get.mock.calls.map(([path]) => path);
		expect(paths).toEqual(expect.arrayContaining([
			'/api/v1/networks', '/api/v1/keypairs', '/api/v1/security-groups', '/api/v1/networks/default', '/api/v1/file-storage',
		]));
	});
});
