export type PostLoginTarget = '/dashboard' | '/select-project';

export interface PostLoginProjectInput {
	project_id?: string | null;
	default_project_id?: string | null;
}

export interface PostLoginProjectResolution {
	projectId: string | null;
	target: PostLoginTarget;
}

function normalizeProjectId(value: string | null | undefined): string | null {
	const trimmed = value?.trim() ?? '';
	return trimmed.length > 0 ? trimmed : null;
}

export function resolvePostLoginProject(input: PostLoginProjectInput): PostLoginProjectResolution {
	const projectId = normalizeProjectId(input.project_id);
	if (projectId) {
		return { projectId, target: '/dashboard' };
	}

	const defaultProjectId = normalizeProjectId(input.default_project_id);
	if (defaultProjectId) {
		return { projectId: defaultProjectId, target: '/dashboard' };
	}

	return { projectId: null, target: '/select-project' };
}
