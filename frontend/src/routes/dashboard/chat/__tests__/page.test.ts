import { describe, expect, it } from 'vitest';

import { load } from '../+page';

describe('/dashboard/chat route', () => {
	it('opens MCP settings only for an OAuth callback result', () => {
		const oauthData = load({
			url: new URL('http://localhost:3080/dashboard/chat?mcp_oauth=connected&mcp_server_id=7')
		} as Parameters<typeof load>[0]);
		const ordinaryData = load({ url: new URL('http://localhost:3080/dashboard/chat?workspace=12') } as Parameters<typeof load>[0]);

		expect(oauthData).toEqual({ workspaceId: null, initialSettingsSection: 'mcp' });
		expect(ordinaryData).toEqual({ workspaceId: 12, initialSettingsSection: 'usage' });
	});
});
