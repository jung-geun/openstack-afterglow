import { afterEach, describe, expect, it, vi } from 'vitest';

import { deriveBrowserApiBase } from './config';

describe('deriveBrowserApiBase', () => {
	it('prefers explicit public_api_base over frontend_base_url', () => {
		expect(
			deriveBrowserApiBase(
				{
					public_api_base: 'https://api.example.com/root/path',
					frontend_base_url: 'https://frontend.example.com/app',
					backend_port: 9000,
				},
				{},
			),
		).toBe('https://api.example.com');
	});

	it('lets PUBLIC_API_BASE override afterglow.conf for docker compose', () => {
		expect(
			deriveBrowserApiBase(
				{
					public_api_base: 'https://cloud.dmslab.re.kr',
					frontend_base_url: 'https://cloud.dmslab.re.kr',
					backend_port: 8000,
				},
				{ PUBLIC_API_BASE: 'http://localhost:8000' },
			),
		).toBe('http://localhost:8000');
	});

	it('falls back to frontend_base_url when public_api_base is empty or invalid', () => {
		expect(
			deriveBrowserApiBase(
				{
					public_api_base: 'not a url',
					frontend_base_url: 'https://afterglow.example.com/app',
					backend_port: 9000,
				},
				{},
			),
		).toBe('https://afterglow.example.com');
	});

	it('uses backend_port for local development when no public origin is configured', () => {
		expect(deriveBrowserApiBase({ backend_port: 8123 }, {})).toBe('http://localhost:8123');
	});
});

describe('frontend CSP branding origins', () => {
	afterEach(() => {
		vi.resetModules();
		vi.doUnmock('$lib/server/config');
	});

	it('allows cross-origin API and uploaded branding origins in img-src', async () => {
		vi.resetModules();
		vi.doMock('$lib/server/config', () => ({
			loadPublicSiteConfig: () => ({
				site_name: 'Afterglow',
				site_description: 'OpenStack VM + OverlayFS 배포 플랫폼',
				logo_path: 'https://uploads.example.com/legacy.png',
				logo_dark_path: '/api/v1/site-config/assets/logo_dark',
				logo_light_path: 'https://cdn.example.com/login-light.png',
				favicon_path: '/favicon.ico',
				refresh_interval_ms: 5000,
				services: { magnum: false, manila: false, zun: false, k3s: false, trove: false, swift: false, barbican: false },
				runtime: {
					api_base: 'https://api.example.com/root/path',
					s3_base: '',
					grafana_base: '',
				},
			}),
		}));

		// Test-only dynamic import: hooks.server must be loaded after vi.doMock so the mocked config module is bound.
		const { handle } = await import('../../hooks.server');
		const response = await handle({
			event: {
				url: new URL('https://frontend.example.com/'),
				locals: {},
				cookies: { get: vi.fn() },
			} as never,
			resolve: vi.fn(async () => new Response('ok', { headers: new Headers() })),
		});

		const csp = response.headers.get('Content-Security-Policy');
		expect(csp).toBeTruthy();
		const imgSrc = csp?.split(';').find((directive) => directive.trimStart().startsWith('img-src'));
		expect(imgSrc).toContain("img-src 'self' data:");
		expect(imgSrc).toContain('https://api.example.com');
		expect(imgSrc).toContain('https://uploads.example.com');
		expect(imgSrc).toContain('https://cdn.example.com');
		expect(response.headers.get('X-Content-Type-Options')).toBe('nosniff');
	});
});
