import { writable, derived } from 'svelte/store';

// /api/auth/me 검증이 성공하면 true. 로그아웃/clearAuth 시 false.
export const authReady = writable(false);

export interface Project {
	id: string;
	name: string;
	description?: string;
	domain_name?: string | null;
	last_accessed_at?: string | null;
}

export interface AuthState {
	token: string | null;           // access JWT
	refreshToken: string | null;    // refresh JWT
	accessExpiresAt: number | null; // access JWT 만료 unix timestamp
	userId: string | null;
	username: string | null;
	projectId: string | null;
	projectName: string | null;
	availableProjects: Project[];
	sessionTimeoutSeconds: number;
	sessionWarningBeforeSeconds: number;
	roles: string[];
	isSystemAdmin: boolean;
	federated: boolean;             // true = OIDC/외부 로그인 (패스워드 변경 불가)
}

const initial: AuthState = {
	token: null,
	refreshToken: null,
	accessExpiresAt: null,
	userId: null,
	username: null,
	projectId: null,
	projectName: null,
	availableProjects: [],
	sessionTimeoutSeconds: 3600,
	sessionWarningBeforeSeconds: 300,
	roles: [],
	isSystemAdmin: false,
	federated: false,
};

function loadPersistedAuth(): AuthState {
	if (typeof window === 'undefined') return initial;
	try {
		const raw = localStorage.getItem('afterglow_auth');
		if (raw) return { ...initial, ...JSON.parse(raw) };
	} catch { /* ignore */ }
	return initial;
}

export const auth = writable<AuthState>(loadPersistedAuth());

// 자동 영속화
if (typeof window !== 'undefined') {
	auth.subscribe(($auth) => {
		// Fix 5: Secure 속성은 HTTPS에서만 부착 — 비-localhost HTTP 배포에서 쿠키 드롭 방지
		const secure = location.protocol === 'https:' ? '; Secure' : '';
		if ($auth.token) {
			localStorage.setItem('afterglow_auth', JSON.stringify($auth));
			document.cookie = `afterglow_session=1; path=/; SameSite=Strict${secure}`;
		} else {
			localStorage.removeItem('afterglow_auth');
			document.cookie = `afterglow_session=; path=/; SameSite=Strict${secure}; max-age=0`;
		}
	});
}

export const isLoggedIn = derived(auth, ($auth) => $auth.token !== null);
export const isAdmin = derived(auth, ($auth) => $auth.isSystemAdmin === true);

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
	authReady.set(false);
	auth.set(initial);
}

/** access JWT의 만료까지 남은 초. 토큰 없으면 0. */
export function getAccessSecondsRemaining(state: AuthState): number {
	if (!state.accessExpiresAt) return 0;
	return Math.max(0, state.accessExpiresAt - Math.floor(Date.now() / 1000));
}
