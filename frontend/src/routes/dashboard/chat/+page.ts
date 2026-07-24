import type { PageLoad } from './$types';

export const load: PageLoad = ({ url }) => {
	const rawWorkspaceId = url.searchParams.get('workspace');
	if (rawWorkspaceId === null) return { workspaceId: null };
	const workspaceId = Number(rawWorkspaceId);
	return { workspaceId: Number.isSafeInteger(workspaceId) && workspaceId > 0 ? workspaceId : null };
};
