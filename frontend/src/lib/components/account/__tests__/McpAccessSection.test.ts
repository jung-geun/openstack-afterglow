import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { clearAuth, setAuth } from '$lib/stores/auth';
import { siteConfig } from '$lib/config/site';

const { api, ApiError, confirmDialog, getBaseUrl } = vi.hoisted(() => ({
	api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
	ApiError: class ApiError extends Error {},
	confirmDialog: vi.fn(),
	getBaseUrl: vi.fn(() => 'https://api.example.test'),
}));

vi.mock('$lib/api/client', () => ({ api, ApiError, getBaseUrl }));
vi.mock('$lib/stores/confirm.svelte', () => ({ confirmDialog }));

import McpAccessSection from '../McpAccessSection.svelte';

const activeToken = {
	id: 'token-1',
	grant_id: 'grant-1',
	name: 'Lumen',
	source: 'personal_token',
	access_level: 'read',
	status: 'active',
	visible_prefix: 'mcp-afgl-example',
	issued_at: '2026-07-27T00:00:00Z',
	expires_at: '2026-08-27T00:00:00Z',
	last_used_at: null,
	revoked_at: null,
	is_lumen_default: true,
};

describe('McpAccessSection', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		clearAuth();
		setAuth({
			token: 'token',
			refreshToken: 'refresh-token',
			userId: 'user',
			username: 'user',
			projectId: 'project',
			projectName: 'Project',
			accessExpiresAt: null,
			roles: [],
		});
		siteConfig.update((config) => ({ ...config, services: { ...config.services, mcp: true } }));
		api.get.mockImplementation((path: string) => Promise.resolve(path.includes('oauth') ? [] : [activeToken]));
		api.post.mockResolvedValue({ ...activeToken, id: 'token-2', grant_id: 'grant-2', token: 'mcp-afgl-secret-value' });
	});

	afterEach(() => {
		siteConfig.update((config) => ({ ...config, services: { ...config.services, mcp: false } }));
	});

	it('shows the current Lumen default without exposing a token secret', async () => {
		render(McpAccessSection);
		expect(screen.getByText('https://api.example.test/api/v1/mcp')).toBeTruthy();

		await waitFor(() => expect(screen.getByText('Lumen 기본 토큰')).toBeTruthy());
		expect(screen.queryByText('mcp-afgl-secret-value')).toBeNull();
		expect(api.get).toHaveBeenCalledWith('/api/v1/auth/mcp-tokens', 'token', 'project');
		expect(api.get).toHaveBeenCalledWith('/api/v1/auth/mcp-oauth/grants', 'token', 'project');
		expect(screen.getByRole('button', { name: 'Lumen 해제' })).toBeTruthy();
	});

	it('displays a newly issued token once after creation', async () => {
		render(McpAccessSection);
		await waitFor(() => expect(screen.getByLabelText(/이름/)).toBeTruthy());

		await fireEvent.input(screen.getByLabelText(/이름/), { target: { value: 'Desktop client' } });
		await fireEvent.click(screen.getByRole('button', { name: '토큰 만들기' }));

		await waitFor(() => expect(screen.getByText('새 MCP 토큰')).toBeTruthy());
		expect(screen.getByText('mcp-afgl-secret-value')).toBeTruthy();
		expect(api.post).toHaveBeenCalledWith(
			'/api/v1/auth/mcp-tokens',
			expect.objectContaining({ name: 'Desktop client', access_level: 'read' }),
			'token',
			'project',
		);
		await fireEvent.click(screen.getByRole('button', { name: '완료' }));
		expect(screen.queryByText('mcp-afgl-secret-value')).toBeNull();
	});
});
