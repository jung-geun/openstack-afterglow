export type MockupProfileId = 'tutorial' | 'admin';

export const MOCKUP_QUERY_KEY = 'mockup';
export const MOCKUP_COOKIE = 'afterglow_mockup';
export const MOCKUP_STORAGE_KEY = 'afterglow_mock_auth';
// sessionStorage keeps the client activation scoped to one browser tab.
export const MOCKUP_SESSION_KEY = 'afterglow_mockup_profile';

export interface MockupSession {
	active: boolean;
	profile: MockupProfileId | null;
	homePath: '/' | '/dashboard' | '/admin';
	allowedPaths: string[];
	bannerLabel: string;
}

const TUTORIAL_ALLOWED_PATHS = [
	'/',
	'/login',
	'/select-project',
	'/dashboard',
	'/dashboard/compute/instances',
	'/dashboard/drover',
	'/dashboard/network/topology',
] as const;

const ADMIN_ALLOWED_PATHS = ['/', '/login', '/admin'] as const;

const PROFILE_ALLOWED_PATHS: Record<MockupProfileId, readonly string[]> = {
	tutorial: TUTORIAL_ALLOWED_PATHS,
	admin: ADMIN_ALLOWED_PATHS,
};

const PROFILE_HOME_PATH: Record<MockupProfileId, MockupSession['homePath']> = {
	tutorial: '/dashboard',
	admin: '/admin',
};

const PROFILE_BANNER_LABEL: Record<MockupProfileId, string> = {
	tutorial: '튜토리얼 mockup',
	admin: '관리자 mockup',
};

export const MOCKUP_SERVICE_OVERRIDES = {
	magnum: true,
	manila: true,
	zun: true,
	k3s: true,
	trove: true,
	swift: true,
	barbican: true,
} as const;

export function isMockupProfileId(value: unknown): value is MockupProfileId {
	return value === 'tutorial' || value === 'admin';
}

export function inactiveMockupSession(): MockupSession {
	return {
		active: false,
		profile: null,
		homePath: '/',
		allowedPaths: [],
		bannerLabel: '',
	};
}

export function buildMockupSession(profile: MockupProfileId): MockupSession {
	return {
		active: true,
		profile,
		homePath: PROFILE_HOME_PATH[profile],
		allowedPaths: [...PROFILE_ALLOWED_PATHS[profile]],
		bannerLabel: PROFILE_BANNER_LABEL[profile],
	};
}

export function isMockupPathAllowed(profile: MockupProfileId, pathname: string): boolean {
	if (PROFILE_ALLOWED_PATHS[profile].includes(pathname)) return true;
	// Tutorial instance detail pages are reached from the supported instance list.
	return profile === 'tutorial' && pathname.startsWith('/dashboard/compute/instances/');
}

export function getMockupHomePath(profile: MockupProfileId): '/dashboard' | '/admin' {
	return PROFILE_HOME_PATH[profile] as '/dashboard' | '/admin';
}
