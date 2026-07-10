import { afterEach, describe, expect, it, vi } from 'vitest';
import type { Handle } from '@sveltejs/kit';

import type { PublicSiteConfig } from '$lib/types/siteConfig';

const baseConfig: PublicSiteConfig = {
	site_name: 'Afterglow',
	site_description: 'OpenStack VM + OverlayFS 배포 플랫폼',
	logo_path: '/logo.png',
	logo_dark_path: '/logo-white.png',
	logo_light_path: '/logo-dark.png',
	favicon_path: '/favicon.ico',
	refresh_interval_ms: 5000,
	services: {
		magnum: false,
		manila: false,
		zun: false,
		k3s: false,
		trove: false,
		swift: false,
		barbican: false,
	},
	runtime: {
		api_base: 'https://api.example.com',
		s3_base: '',
		grafana_base: '',
	},
};

type CookieJar = Record<string, string | undefined>;

function createRequest(url: string, initialCookies: CookieJar = {}, routeId: string | null = '/[...path]') {
	const jar = { ...initialCookies };
	const cookies = {
		get: vi.fn((name: string) => jar[name]),
		set: vi.fn((name: string, value: string) => {
			jar[name] = value;
		}),
		delete: vi.fn((name: string) => {
			delete jar[name];
		}),
	};
	const event = {
		url: new URL(url),
		locals: {},
		cookies,
		route: { id: routeId },
	} as unknown as Parameters<Handle>[0]['event'];
	const resolve = vi.fn(async () => new Response('ok', { status: 200, headers: new Headers() }));
	return { cookies, event, resolve, jar };
}

async function loadHandle() {
	vi.resetModules();
	vi.doMock('$lib/server/config', () => ({
		loadPublicSiteConfig: () => baseConfig,
	}));
	// Dynamic import required: hooks.server reads the mocked config module during module evaluation.
	return import('./hooks.server');
}

afterEach(() => {
	vi.resetModules();
	vi.doUnmock('$lib/server/config');
});

describe('hooks.server mockup gating', () => {
	it('redirects logged-out protected routes to /login when mockup mode is off', async () => {
		const { handle } = await loadHandle();
		const request = createRequest('http://frontend.example.com/dashboard');

		const response = await handle({ event: request.event, resolve: request.resolve });

		expect(response.status).toBe(302);
		expect(response.headers.get('Location')).toBe('/login');
		expect(request.resolve).not.toHaveBeenCalled();
	});

	it('bootstraps tutorial mockup from the query without persisting a browser-wide cookie', async () => {
		const { handle } = await loadHandle();
		const request = createRequest('http://frontend.example.com/dashboard?mockup=tutorial');

		const response = await handle({ event: request.event, resolve: request.resolve });

		expect(response.status).toBe(200);
		expect(request.resolve).toHaveBeenCalledOnce();
		expect(request.cookies.set).not.toHaveBeenCalled();
		expect(request.event.locals).toMatchObject({
			mockup: {
				active: true,
				profile: 'tutorial',
				homePath: '/dashboard',
			},
		});
	});

	it('redirects unsupported tutorial paths to a query-bearing home route', async () => {
		const { handle } = await loadHandle();
		const request = createRequest('http://frontend.example.com/dashboard/volumes?mockup=tutorial');

		const response = await handle({ event: request.event, resolve: request.resolve });

		expect(response.status).toBe(302);
		expect(response.headers.get('Location')).toBe('/dashboard?mockup=tutorial');
		expect(request.resolve).not.toHaveBeenCalled();
		expect(request.cookies.set).not.toHaveBeenCalled();
	});

	it('blocks an admin dynamic route even when its parameter looks like a static asset', async () => {
		const { handle } = await loadHandle();
		const request = createRequest('http://frontend.example.com/dashboard/compute/instances/not-allowed.png?mockup=admin');

		const response = await handle({ event: request.event, resolve: request.resolve });

		expect(response.status).toBe(302);
		expect(response.headers.get('Location')).toBe('/admin?mockup=admin');
		expect(request.resolve).not.toHaveBeenCalled();
	});

	it('keeps the profile allowlist active when a real session cookie is also present', async () => {
		const { handle } = await loadHandle();
		const request = createRequest(
			'http://frontend.example.com/dashboard/volumes?mockup=tutorial',
			{ afterglow_session: 'active-session' },
		);

		const response = await handle({ event: request.event, resolve: request.resolve });

		expect(response.status).toBe(302);
		expect(response.headers.get('Location')).toBe('/dashboard?mockup=tutorial');
		expect(request.resolve).not.toHaveBeenCalled();
	});
});
