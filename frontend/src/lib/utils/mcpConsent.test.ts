import { afterEach, describe, expect, it } from 'vitest';
import {
	clearMcpConsentTicket,
	pendingMcpConsentTicket,
	postAuthDestination,
	storeMcpConsentTicket,
} from './mcpConsent';

const ticket = 'A'.repeat(43);

afterEach(() => {
	sessionStorage.clear();
});

describe('MCP OAuth consent handoff', () => {
	it('persists only a valid ticket long enough to return after authentication', () => {
		expect(storeMcpConsentTicket(ticket)).toBe(true);
		expect(pendingMcpConsentTicket()).toBe(ticket);
		expect(postAuthDestination('/dashboard')).toBe('/oauth/mcp/authorize');
	});

	it('rejects malformed ticket values and clears the route destination after use', () => {
		expect(storeMcpConsentTicket('not a ticket')).toBe(false);
		expect(pendingMcpConsentTicket()).toBeNull();
		clearMcpConsentTicket();
		expect(postAuthDestination('/dashboard')).toBe('/dashboard');
	});
});
