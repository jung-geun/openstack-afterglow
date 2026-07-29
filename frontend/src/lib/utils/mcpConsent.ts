const CONSENT_TICKET_KEY = 'afterglow_mcp_oauth_consent_ticket';
const TICKET_PATTERN = /^[A-Za-z0-9_-]{32,128}$/;

function storage(): Storage | null {
	if (typeof window === 'undefined') return null;
	return window.sessionStorage;
}

export function storeMcpConsentTicket(ticket: string): boolean {
	if (!TICKET_PATTERN.test(ticket)) return false;
	storage()?.setItem(CONSENT_TICKET_KEY, ticket);
	return true;
}

export function pendingMcpConsentTicket(): string | null {
	const ticket = storage()?.getItem(CONSENT_TICKET_KEY) ?? null;
	return ticket && TICKET_PATTERN.test(ticket) ? ticket : null;
}

export function clearMcpConsentTicket(): void {
	storage()?.removeItem(CONSENT_TICKET_KEY);
}

export function postAuthDestination(fallback: string): string {
	return pendingMcpConsentTicket() ? '/oauth/mcp/authorize' : fallback;
}
