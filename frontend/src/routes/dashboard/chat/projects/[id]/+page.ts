import { error } from '@sveltejs/kit';
import type { PageLoad } from './$types';

export const load: PageLoad = ({ params }) => {
	const workspaceId = Number(params.id);
	if (!Number.isSafeInteger(workspaceId) || workspaceId < 1) error(404, '프로젝트를 찾을 수 없습니다');
	return { workspaceId };
};
