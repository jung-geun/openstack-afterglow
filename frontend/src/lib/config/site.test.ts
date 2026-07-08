import { beforeEach, describe, expect, it } from 'vitest';
import { get } from 'svelte/store';
import type { PublicSiteConfig } from '$lib/types/siteConfig';
import { initSiteConfig, qualifyBackendAssetPaths, siteConfig } from './site';

const baseConfig: PublicSiteConfig = {
	site_name: 'Afterglow',
	site_description: 'OpenStack VM + OverlayFS 배포 플랫폼',
	logo_path: '/logo.png',
	logo_dark_path: '/logo-dark.png',
	logo_light_path: '/logo-white.png',
	favicon_path: '/favicon.ico',
	refresh_interval_ms: 5000,
	services: { magnum: false, manila: false, zun: false, k3s: false, trove: false, swift: false, barbican: false },
	runtime: {
		api_base: 'https://api.example.com',
		s3_base: '',
		grafana_base: '',
	},
};

function resetSiteConfig() {
	siteConfig.set({
		...baseConfig,
		services: { ...baseConfig.services },
		runtime: { ...baseConfig.runtime },
	});
}

describe('site config refresh', () => {
	beforeEach(() => {
		resetSiteConfig();
	});

	it('qualifies backend asset paths and keeps runtime.api_base during the public config refresh merge', () => {
		const refreshed = qualifyBackendAssetPaths(
			{
				logo_light_path: '/api/v1/site-config/assets/logo_light',
				logo_dark_path: '/api/v1/site-config/assets/logo_dark',
			},
			get(siteConfig).runtime.api_base,
		);

		initSiteConfig(refreshed);

		expect(get(siteConfig)).toMatchObject({
			logo_light_path: 'https://api.example.com/api/v1/site-config/assets/logo_light',
			logo_dark_path: 'https://api.example.com/api/v1/site-config/assets/logo_dark',
			runtime: { api_base: 'https://api.example.com' },
		});
	});

	it('leaves static and already-absolute asset paths untouched when qualifying backend paths', () => {
		expect(
			qualifyBackendAssetPaths(
				{
					logo_path: '/logo.png',
					logo_light_path: 'https://cdn.example.com/login-light.png',
					favicon_path: '/favicon.ico',
				},
				'https://api.example.com',
			),
		).toEqual({
			logo_path: '/logo.png',
			logo_light_path: 'https://cdn.example.com/login-light.png',
			favicon_path: '/favicon.ico',
		});
	});
});
