import type { PageLoad } from './$types';

export const load: PageLoad = ({ url }) => {
	const rawWorkspaceId = url.searchParams.get('workspace');
	const workspaceId = Number(rawWorkspaceId);
	const mcpOauthResult = url.searchParams.get('mcp_oauth');
	return {
		workspaceId: Number.isSafeInteger(workspaceId) && workspaceId > 0 ? workspaceId : null,
		initialSettingsSection: mcpOauthResult === 'connected' || mcpOauthResult === 'failed' ? 'mcp' : 'usage'
	};
};
