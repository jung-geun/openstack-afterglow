import { render, screen, waitFor } from '@testing-library/svelte';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { auth } from '$lib/stores/auth';

const mocks = vi.hoisted(() => ({
	get: vi.fn(),
	post: vi.fn(),
	patch: vi.fn(),
	put: vi.fn(),
	delete: vi.fn(),
	confirm: vi.fn(),
	toast: { error: vi.fn(), success: vi.fn() }
}));

vi.mock('$lib/api/client', () => ({
	api: { get: mocks.get, post: mocks.post, patch: mocks.patch, put: mocks.put, delete: mocks.delete },
	ApiError: class ApiError extends Error {}
}));
vi.mock('$lib/stores/confirm.svelte', () => ({ confirmDialog: mocks.confirm }));
vi.mock('$lib/stores/toast', () => ({ toast: mocks.toast }));

import ChatExtensionsManager from '../ChatExtensionsManager.svelte';

describe('ChatExtensionsManager MCP OAuth', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		auth.set({
			token: 'token',
			refreshToken: null,
			accessExpiresAt: null,
			userId: 'user-1',
			username: 'tester',
			projectId: 'project-1',
			projectName: 'Project',
			availableProjects: [],
			roles: [],
			isSystemAdmin: false,
			federated: false
		});
		mocks.get.mockImplementation((path: string) => {
			if (path.endsWith('/mcp-servers')) {
				return Promise.resolve([
					{
						id: 7,
						name: 'Notion',
						scope: 'global',
						transport: 'http',
						url: 'https://mcp.notion.com/mcp',
						auth_mode: 'oauth',
						is_active: true
					}
				]);
			}
			if (path.endsWith('/oauth')) return Promise.resolve({ required: true, connected: false, expires_at: null });
			return Promise.resolve([]);
		});
	});

	it('shows a per-user Notion connection action instead of requesting a static token', async () => {
		render(ChatExtensionsManager, { base: '/api/v1/chat', only: 'mcp' });

		await waitFor(() => expect(screen.getByRole('button', { name: 'Notion OAuth 연결' })).toBeTruthy());
		expect(screen.queryByText('Notion Integration Token')).toBeNull();
		expect(mocks.get).toHaveBeenCalledWith('/api/v1/chat/mcp-servers/7/oauth', 'token', 'project-1');
	});
});
