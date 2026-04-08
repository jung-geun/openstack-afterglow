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
// 동시에 서버 사이드 인증 미들웨어(hooks.server.ts)를 위한 마커 쿠키도 관리
if (typeof window !== 'undefined') {
	auth.subscribe(($auth) => {
		if ($auth.token) {
			localStorage.setItem('union_auth', JSON.stringify($auth));
			// 서버 사이드 라우트 보호용 마커 쿠키 (httpOnly 아님 — 토큰 자체는 저장하지 않음)
			document.cookie = 'union_session=1; path=/; SameSite=Strict; Secure';
		} else {
			localStorage.removeItem('union_auth');
			document.cookie = 'union_session=; path=/; SameSite=Strict; Secure; max-age=0';
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
