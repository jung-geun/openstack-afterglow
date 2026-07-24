import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/svelte';
import { writable } from 'svelte/store';
import type { ZunContainer } from '$lib/types/zunContainer';

const { goto, api } = vi.hoisted(() => ({
	goto: vi.fn(),
	api: {
		get: vi.fn(),
		post: vi.fn(),
		delete: vi.fn(),
	},
}));

vi.mock('$app/navigation', () => ({ goto }));
vi.mock('$lib/api/client', () => ({
	api,
	ApiError: class ApiError extends Error { status = 500; },
}));
vi.mock('$lib/stores/auth', () => ({
	auth: writable({ token: 'token', projectId: 'project' }),
}));

import Page from '../+page.svelte';

const container: ZunContainer = {
	uuid: 'running-1',
	name: 'running',
	status: 'Running',
	status_reason: null,
	image: 'alpine',
	command: null,
	cpu: 1,
	memory: '512M',
	created_at: '2026-01-01T00:00:00Z',
};

describe('container instances page', () => {
	beforeEach(() => {
		goto.mockReset();
		api.get.mockResolvedValue({ items: [container], service_available: true, message: '' });
	});

	it('wires a container name to its detail route', async () => {
		render(Page);

		await fireEvent.click(await screen.findByRole('button', { name: 'running' }));
		expect(goto).toHaveBeenCalledWith('/dashboard/containers/instances/running-1');
	});
});
