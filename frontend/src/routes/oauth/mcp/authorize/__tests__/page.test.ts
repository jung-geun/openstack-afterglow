import { render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MOCK_MCP_CONSENT_TICKET } from '$lib/mockup/contracts';
import { pendingMcpConsentTicket } from '$lib/utils/mcpConsent';
const { api, auth, goto, page } = vi.hoisted(() => {
	let value = { url: new URL('http://localhost/oauth/mcp/authorize'), data: {} };
	const subscribers = new Set<(next: typeof value) => void>();
	return {
		api: { get: vi.fn(), post: vi.fn() },
		auth: {
			subscribe(run: (next: { token: string; projectId: string }) => void) {
				run({ token: 'mock-token', projectId: 'mock-project-1' });
				return () => {};
			},
		},
		goto: vi.fn(),
		page: {
			subscribe(run: (next: typeof value) => void) {
				subscribers.add(run);
				run(value);
				return () => subscribers.delete(run);
			},
			set(next: typeof value) {
				value = next;
				for (const run of subscribers) run(value);
			},
		},
	};
});

vi.mock('$app/navigation', () => ({ goto }));
vi.mock('$app/stores', () => ({ page }));
vi.mock('$lib/api/client', () => ({
	api,
	ApiError: class ApiError extends Error {},
}));
vi.mock('$lib/stores/auth', () => ({ auth }));

import Page from '../+page.svelte';

describe('MCP OAuth consent route', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		sessionStorage.clear();
		page.set({
			url: new URL(`http://localhost/oauth/mcp/authorize?ticket=${MOCK_MCP_CONSENT_TICKET}`),
			data: {},
		});
		api.get.mockResolvedValue({
			client_id: 'mock-mcp-desktop-client',
			client_name: 'Tutorial Desktop MCP',
			redirect_uri: 'http://mock-client.example.test/oauth/callback',
			scopes: ['mcp:read'],
			grant_deadline: '2026-12-31T23:59:59Z',
		});
	});

	afterEach(() => {
		sessionStorage.clear();
	});

	it('stores a valid ticket, scrubs it from the address bar, and loads only the bound consent details', async () => {
		const replaceState = vi.spyOn(history, 'replaceState');

		render(Page);

		expect(await screen.findByText('Tutorial Desktop MCP')).toBeTruthy();
		expect(pendingMcpConsentTicket()).toBe(MOCK_MCP_CONSENT_TICKET);
		expect(replaceState).toHaveBeenCalledWith(null, '', '/oauth/mcp/authorize');
		expect(api.get).toHaveBeenCalledWith(
			`/api/v1/auth/mcp-oauth/consents/${MOCK_MCP_CONSENT_TICKET}`,
			'mock-token',
			'mock-project-1',
		);
		expect(goto).not.toHaveBeenCalled();
	});

	it('rejects malformed query tickets without calling the consent API', async () => {
		page.set({ url: new URL('http://localhost/oauth/mcp/authorize?ticket=invalid'), data: {} });

		render(Page);

		await waitFor(() => expect(screen.getByText('OAuth 승인 요청이 유효하지 않습니다.')).toBeTruthy());
		expect(pendingMcpConsentTicket()).toBeNull();
		expect(api.get).not.toHaveBeenCalled();
	});
});
