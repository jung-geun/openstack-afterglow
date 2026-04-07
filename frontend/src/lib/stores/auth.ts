import { writable, derived } from 'svelte/store';

interface Project {
	id: string;
	name: string;
	description?: string;
}

export interface AuthState {
	token: string | null;
	userId: string | null;
	username: string | null;
	projectId: string | null;
	projectName: string | null;
	availableProjects: Project[];
	expiresAt: string | null;
	sessionTimeoutSeconds: number;
	sessionWarningBeforeSeconds: number;
	roles: string[];
}

const initial: AuthState = {
	token: null,
	userId: null,
	username: null,
	projectId: null,
	projectName: null,
	availableProjects: [],
	expiresAt: null,
	sessionTimeoutSeconds: 3600,
	sessionWarningBeforeSeconds: 300,
	roles: [],
};

function loadPersistedAuth(): AuthState {
	if (typeof window === 'undefined') return initial;
	try {
		const raw = localStorage.getItem('union_auth');
		if (raw) return { ...initial, ...JSON.parse(raw) };
	} catch { /* ignore */ }
	return initial;
}

export const auth = writable<AuthState>(loadPersistedAuth());

// 자동 영속화: token이 있으면 localStorage에 저장, 없으면 제거
if (typeof window !== 'undefined') {
	auth.subscribe(($auth) => {
		if ($auth.token) {
			localStorage.setItem('union_auth', JSON.stringify($auth));
		} else {
			localStorage.removeItem('union_auth');
		}
	});
}

export const isLoggedIn = derived(auth, ($auth) => $auth.token !== null);
export const isAdmin = derived(auth, ($auth) => $auth.roles.includes('admin'));

export function setAuth(data: Partial<AuthState> & { token: string }) {
	auth.update((state) => ({
		...state,
		...data
	}));
}

export function setProject(projectId: string, projectName: string) {
	auth.update((state) => ({
		...state,
		projectId,
		projectName
	}));
}

export function setAvailableProjects(projects: Project[]) {
	auth.update((state) => ({
		...state,
		availableProjects: projects
	}));
}

export function clearAuth() {
	auth.set(initial);
}
